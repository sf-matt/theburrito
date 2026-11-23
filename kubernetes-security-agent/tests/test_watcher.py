from types import SimpleNamespace

import pytest
from kubernetes.client import (
    V1Container,
    V1ObjectMeta,
    V1Pod,
    V1PodSpec,
    V1SecurityContext,
)

from agent.models import SecurityFinding, WorkloadIdentity
from agent.registry import InvestigationRegistry, InvestigationStatus
from agent.watcher import InvestigationWorker, PodWatcher


class RecordingWorker:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0
        self.findings = []

    def start(self) -> None:
        self.started += 1

    def stop(self) -> None:
        self.stopped += 1

    def submit(self, finding: SecurityFinding) -> None:
        self.findings.append(finding)


def privileged_pod() -> V1Pod:
    return V1Pod(
        metadata=V1ObjectMeta(
            name="risky-pod",
            namespace="ai-lab",
            uid="uid-1",
            resource_version="10",
        ),
        spec=V1PodSpec(
            containers=[
                V1Container(
                    name="risky",
                    image="example.invalid/risky:1",
                    security_context=V1SecurityContext(privileged=True),
                )
            ]
        ),
    )


def finding(name: str, uid: str) -> SecurityFinding:
    return SecurityFinding(
        namespace="ai-lab",
        pod_name=name,
        pod_uid=uid,
        container_name="risky",
        detection_reason="privileged",
        relevant_security_configuration={"privileged": True},
        workload=WorkloadIdentity(
            api_version="v1",
            kind="Pod",
            namespace="ai-lab",
            name=name,
            uid=uid,
        ),
        fingerprint=f"fingerprint-{uid}",
    )


def test_relist_processes_existing_pods_and_returns_resource_version() -> None:
    api = SimpleNamespace(
        list_pod_for_all_namespaces=lambda **kwargs: SimpleNamespace(
            items=[privileged_pod()],
            metadata=SimpleNamespace(resource_version="10"),
        )
    )
    worker = RecordingWorker()
    watcher = PodWatcher(
        api=api,
        label_selector=None,
        worker=worker,
    )

    assert watcher._relist() == "10"
    assert [finding.container_name for finding in worker.findings] == ["risky"]


def test_nonprivileged_pod_skips_owner_resolution() -> None:
    class UnexpectedResolver:
        def resolve(self, pod):
            raise AssertionError("owner resolution should not run")

    pod = V1Pod(
        metadata=V1ObjectMeta(name="ordinary", namespace="default", uid="uid-ordinary"),
        spec=V1PodSpec(
            containers=[V1Container(name="ordinary", image="example.invalid/app:1")]
        ),
    )
    worker = RecordingWorker()
    watcher = PodWatcher(
        api=SimpleNamespace(),
        label_selector=None,
        worker=worker,
        workload_resolver=UnexpectedResolver(),
    )

    watcher._process_pod(pod)

    assert worker.findings == []


def test_expired_watch_resource_version_triggers_relist(monkeypatch) -> None:
    list_calls = []

    def list_pod_for_all_namespaces(**kwargs):
        list_calls.append(kwargs)
        return SimpleNamespace(
            items=[], metadata=SimpleNamespace(resource_version=str(len(list_calls)))
        )

    class FakeWatch:
        calls = 0

        def stream(self, *args, **kwargs):
            FakeWatch.calls += 1
            if FakeWatch.calls == 1:
                yield {
                    "type": "ERROR",
                    "object": SimpleNamespace(code=410, metadata=None),
                }
            else:
                raise KeyboardInterrupt

    monkeypatch.setattr("agent.watcher.watch.Watch", FakeWatch)
    worker = RecordingWorker()
    watcher = PodWatcher(
        api=SimpleNamespace(list_pod_for_all_namespaces=list_pod_for_all_namespaces),
        label_selector=None,
        worker=worker,
    )

    with pytest.raises(KeyboardInterrupt):
        watcher.run()

    assert len(list_calls) == 2
    assert all("namespace" not in call for call in list_calls)
    assert worker.started == 1
    assert worker.stopped == 1


def test_queue_overflow_marks_finding_failed() -> None:
    registry = InvestigationRegistry(cooldown_seconds=60)
    worker = InvestigationWorker(
        registry=registry,
        investigator=None,
        dry_run=True,
        queue_size=1,
    )
    first = finding("first", "uid-1")
    second = finding("second", "uid-2")

    worker.submit(first)
    worker.submit(second)

    assert registry.get(second).status == InvestigationStatus.FAILED
    assert worker.counters.failed == 1


def test_worker_failure_is_recorded() -> None:
    class FailingInvestigator:
        def investigate(self, finding: SecurityFinding) -> str:
            raise RuntimeError("simulated investigation failure")

    registry = InvestigationRegistry(cooldown_seconds=60)
    worker = InvestigationWorker(
        registry=registry,
        investigator=FailingInvestigator(),
        dry_run=False,
    )
    failed_finding = finding("risky-pod", "uid-failure")

    worker.start()
    worker.submit(failed_finding)
    worker.queue.join()
    worker.stop()

    assert registry.get(failed_finding).status == InvestigationStatus.FAILED
    assert worker.counters.failed == 1
