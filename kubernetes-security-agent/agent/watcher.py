from __future__ import annotations

import json
import logging
import queue
import threading
import time
from dataclasses import dataclass
from kubernetes import client, watch
from kubernetes.client.exceptions import ApiException
from urllib3.exceptions import HTTPError

from .detector import detect_privileged_containers, has_privileged_container
from .investigator_protocol import Investigator
from .kube import WorkloadResolver
from .models import SecurityFinding
from .registry import InvestigationRegistry


LOGGER = logging.getLogger(__name__)


@dataclass
class InvestigationCounters:
    detected: int = 0
    queued: int = 0
    skipped_duplicate: int = 0
    completed: int = 0
    failed: int = 0


class InvestigationWorker:
    def __init__(
        self,
        *,
        registry: InvestigationRegistry,
        investigator: Investigator | None,
        dry_run: bool,
        queue_size: int = 100,
    ) -> None:
        self.registry = registry
        self.investigator = investigator
        self.dry_run = dry_run
        self.queue: queue.Queue[SecurityFinding | None] = queue.Queue(queue_size)
        self.counters = InvestigationCounters()
        self._thread = threading.Thread(
            target=self._run, name="investigation-worker", daemon=True
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self.queue.put(None)
        self._thread.join()

    def submit(self, finding: SecurityFinding) -> None:
        self.counters.detected += 1
        if not self.registry.begin(finding, observation_only=self.dry_run):
            self.counters.skipped_duplicate += 1
            LOGGER.debug(
                "Duplicate finding skipped",
                extra={
                    "namespace": finding.namespace,
                    "pod_name": finding.pod_name,
                    "container_name": finding.container_name,
                    "skipped_duplicate_count": self.counters.skipped_duplicate,
                },
            )
            return
        LOGGER.warning(
            "New privileged workload fingerprint detected",
            extra={
                "namespace": finding.namespace,
                "pod_name": finding.pod_name,
                "workload_kind": finding.workload.kind,
                "workload_name": finding.workload.name,
                "container_name": finding.container_name,
                "detection_reason": finding.detection_reason,
            },
        )
        try:
            self.queue.put_nowait(finding)
        except queue.Full:
            self.registry.fail(finding)
            self.counters.failed += 1
            self._log_counters("Investigation queue is full", level=logging.ERROR)
            return
        self.counters.queued += 1
        self._log_counters("Finding queued")

    def _run(self) -> None:
        while True:
            finding = self.queue.get()
            try:
                if finding is None:
                    return
                LOGGER.info(
                    "Investigation started",
                    extra={"pod_name": finding.pod_name, "dry_run": self.dry_run},
                )
                if self.dry_run:
                    assessment = None
                    LOGGER.info(
                        "Dry-run finding",
                        extra={"finding": json.dumps(finding.to_dict(), sort_keys=True)},
                    )
                else:
                    if self.investigator is None:
                        raise RuntimeError("investigator is not configured")
                    assessment = self.investigator.investigate(finding)
                    LOGGER.info(
                        "Investigation assessment",
                        extra={
                            "namespace": finding.namespace,
                            "pod_name": finding.pod_name,
                            "disposition": assessment.disposition.value,
                            "assessment": json.dumps(
                                assessment.to_dict(), sort_keys=True
                            ),
                        },
                    )
                self.registry.complete(finding, assessment)
                self.counters.completed += 1
                self._log_counters("Investigation completed")
            except Exception:
                if finding is not None:
                    self.registry.fail(finding)
                self.counters.failed += 1
                self._log_counters(
                    "Investigation failed", level=logging.ERROR, exc_info=True
                )
            finally:
                self.queue.task_done()

    def _log_counters(
        self, message: str, *, level: int = logging.INFO, exc_info: bool = False
    ) -> None:
        LOGGER.log(
            level,
            message,
            extra={
                "detected_count": self.counters.detected,
                "queued_count": self.counters.queued,
                "skipped_duplicate_count": self.counters.skipped_duplicate,
                "completed_count": self.counters.completed,
                "failed_count": self.counters.failed,
            },
            exc_info=exc_info,
        )


class PodWatcher:
    def __init__(
        self,
        *,
        api: client.CoreV1Api,
        label_selector: str | None,
        worker: InvestigationWorker,
        workload_resolver: WorkloadResolver | None = None,
    ) -> None:
        self.api = api
        self.label_selector = label_selector
        self.worker = worker
        self.workload_resolver = workload_resolver

    def run(self) -> None:
        resource_version: str | None = None
        reconnect_delay = 1
        self.worker.start()
        try:
            while True:
                if resource_version is None:
                    try:
                        resource_version = self._relist()
                        reconnect_delay = 1
                    except (ApiException, HTTPError, OSError, TimeoutError) as exc:
                        LOGGER.warning(
                            "Pod list failed; retrying",
                            extra={
                                "error_type": type(exc).__name__,
                                "reconnect_delay_seconds": reconnect_delay,
                            },
                        )
                        time.sleep(reconnect_delay)
                        reconnect_delay = min(reconnect_delay * 2, 30)
                        continue
                LOGGER.info(
                    "Opening Pod watch",
                    extra={
                        "scope": "all_namespaces",
                        "resource_version": resource_version,
                    },
                )
                watcher = watch.Watch()
                try:
                    for event in watcher.stream(
                        self.api.list_pod_for_all_namespaces,
                        label_selector=self.label_selector,
                        resource_version=resource_version,
                        timeout_seconds=60,
                        allow_watch_bookmarks=True,
                    ):
                        event_type = event.get("type")
                        pod = event.get("object")
                        metadata = getattr(pod, "metadata", None)
                        if metadata is not None and metadata.resource_version:
                            resource_version = metadata.resource_version
                        if event_type in {"ADDED", "MODIFIED"}:
                            self._process_pod(pod)
                        elif event_type == "ERROR" and getattr(pod, "code", None) == 410:
                            raise ApiException(status=410, reason="resource version expired")
                        reconnect_delay = 1
                    LOGGER.info("Pod watch timed out; reconnecting")
                except ApiException as exc:
                    if exc.status == 410:
                        LOGGER.warning(
                            "Pod watch resource version expired; relisting"
                        )
                        resource_version = None
                        continue
                    LOGGER.warning(
                        "Kubernetes watch request failed; reconnecting",
                        extra={
                            "status_code": exc.status,
                            "reconnect_delay_seconds": reconnect_delay,
                        },
                    )
                    time.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, 30)
                except (HTTPError, OSError, TimeoutError) as exc:
                    LOGGER.warning(
                        "Pod watch connection failed; reconnecting",
                        extra={
                            "error_type": type(exc).__name__,
                            "reconnect_delay_seconds": reconnect_delay,
                        },
                    )
                    time.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, 30)
        finally:
            self.worker.stop()

    def _relist(self) -> str | None:
        LOGGER.info("Listing Pods before watch", extra={"scope": "all_namespaces"})
        pod_list = self.api.list_pod_for_all_namespaces(
            label_selector=self.label_selector,
        )
        for pod in pod_list.items:
            self._process_pod(pod)
        metadata = pod_list.metadata
        return metadata.resource_version if metadata is not None else None

    def _process_pod(self, pod: object) -> None:
        if not has_privileged_container(pod):
            return
        try:
            workload = (
                self.workload_resolver.resolve(pod)
                if self.workload_resolver is not None
                else None
            )
        except ValueError as exc:
            LOGGER.warning("Pod ownership could not be resolved", extra={"error": str(exc)})
            return
        for finding in detect_privileged_containers(pod, workload):
            self.worker.submit(finding)
