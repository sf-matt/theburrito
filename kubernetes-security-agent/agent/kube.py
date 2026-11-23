from __future__ import annotations

import logging
import re
from collections import OrderedDict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from kubernetes import client, config
from kubernetes.client import (
    V1Container,
    V1EphemeralContainer,
    V1ObjectMeta,
    V1OwnerReference,
    V1Pod,
)
from kubernetes.client.exceptions import ApiException

from .models import WorkloadIdentity


_DNS_SUBDOMAIN = re.compile(
    r"^(?=.{1,253}$)[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?$"
)
_DNS_LABEL = re.compile(r"^(?=.{1,63}$)[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$")
LOGGER = logging.getLogger(__name__)
MAX_NAMESPACE_PODS = 50


def load_core_api(kubeconfig: str) -> client.CoreV1Api:
    _, active_context = config.list_kube_config_contexts(config_file=kubeconfig)
    if active_context is None:
        raise ValueError("KUBECONFIG has no active context")

    client_configuration = client.Configuration()
    config.load_kube_config(
        config_file=kubeconfig,
        client_configuration=client_configuration,
        persist_config=False,
    )
    context = active_context.get("context", {})
    LOGGER.info(
        "Loaded dedicated Kubernetes client",
        extra={
            "kubeconfig_path": str(Path(kubeconfig).resolve()),
            "kube_context": active_context.get("name"),
            "kube_cluster": context.get("cluster"),
            "kube_user": context.get("user"),
            "kube_api_host": client_configuration.host,
        },
    )
    return client.CoreV1Api(client.ApiClient(client_configuration))


def iter_container_groups(
    pod: V1Pod,
) -> Iterable[tuple[str, V1Container | V1EphemeralContainer]]:
    spec = pod.spec
    if spec is None:
        return
    for container in spec.containers or []:
        yield ("container", container)
    for container in spec.init_containers or []:
        yield ("initContainer", container)
    for container in spec.ephemeral_containers or []:
        yield ("ephemeralContainer", container)


def _controller_owner(metadata: V1ObjectMeta | None) -> V1OwnerReference | None:
    if metadata is None:
        return None
    return next(
        (item for item in metadata.owner_references or [] if item.controller),
        None,
    )


def _identity_from_owner(
    owner: V1OwnerReference,
    namespace: str,
) -> WorkloadIdentity:
    return WorkloadIdentity(
        api_version=owner.api_version,
        kind=owner.kind,
        namespace=namespace,
        name=owner.name,
        uid=str(owner.uid),
    )


class WorkloadResolver:
    def __init__(
        self,
        apps_api: client.AppsV1Api,
        batch_api: client.BatchV1Api,
        cache_size: int = 1024,
    ) -> None:
        if cache_size < 1:
            raise ValueError("workload cache size must be at least 1")
        self.apps_api = apps_api
        self.batch_api = batch_api
        self.cache_size = cache_size
        self._cache: OrderedDict[str, WorkloadIdentity] = OrderedDict()

    @classmethod
    def from_core_api(cls, api: client.CoreV1Api) -> "WorkloadResolver":
        return cls(
            apps_api=client.AppsV1Api(api.api_client),
            batch_api=client.BatchV1Api(api.api_client),
        )

    def resolve(self, pod: V1Pod) -> WorkloadIdentity:
        metadata = pod.metadata
        if metadata is None or not metadata.namespace or not metadata.name or not metadata.uid:
            raise ValueError("Pod metadata is incomplete")
        namespace = metadata.namespace
        owner = _controller_owner(metadata)
        if owner is None:
            return WorkloadIdentity(
                api_version="v1",
                kind="Pod",
                namespace=namespace,
                name=metadata.name,
                uid=str(metadata.uid),
            )

        immediate = _identity_from_owner(owner, namespace)
        cache_key = f"{namespace}:{owner.uid}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._cache.move_to_end(cache_key)
            return cached
        try:
            if owner.kind == "ReplicaSet" and owner.api_version.startswith("apps/"):
                replica_set = self.apps_api.read_namespaced_replica_set(
                    name=owner.name,
                    namespace=namespace,
                )
                parent = _controller_owner(replica_set.metadata)
                resolved = (
                    _identity_from_owner(parent, namespace)
                    if parent is not None
                    else immediate
                )
                self._cache_identity(cache_key, resolved)
                return resolved
            if owner.kind == "Job" and owner.api_version.startswith("batch/"):
                job = self.batch_api.read_namespaced_job(
                    name=owner.name,
                    namespace=namespace,
                )
                parent = _controller_owner(job.metadata)
                resolved = (
                    _identity_from_owner(parent, namespace)
                    if parent is not None
                    else immediate
                )
                self._cache_identity(cache_key, resolved)
                return resolved
        except ApiException as exc:
            LOGGER.warning(
                "Could not resolve top-level workload; using immediate owner",
                extra={
                    "namespace": namespace,
                    "owner_kind": owner.kind,
                    "owner_name": owner.name,
                    "status_code": exc.status,
                },
            )
            return immediate
        self._cache_identity(cache_key, immediate)
        return immediate

    def _cache_identity(self, key: str, identity: WorkloadIdentity) -> None:
        self._cache[key] = identity
        self._cache.move_to_end(key)
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)


def validate_pod_reference(
    *, namespace: object, pod_name: object
) -> tuple[str, str]:
    valid_namespace = validate_namespace(namespace)
    if not isinstance(pod_name, str) or not _DNS_SUBDOMAIN.fullmatch(pod_name):
        raise ValueError("pod_name must be a valid Kubernetes DNS subdomain")
    return valid_namespace, pod_name


def validate_namespace(namespace: object) -> str:
    if not isinstance(namespace, str) or not _DNS_LABEL.fullmatch(namespace):
        raise ValueError("namespace must be a valid Kubernetes DNS label")
    return namespace


def _container_summary(
    container: V1Container | V1EphemeralContainer,
) -> dict[str, Any]:
    security_context = container.security_context
    return _without_none({
        "name": container.name,
        "image": container.image,
        "security_context": {
            "privileged": (
                security_context.privileged if security_context is not None else None
            ),
            "allow_privilege_escalation": (
                security_context.allow_privilege_escalation
                if security_context is not None
                else None
            ),
            "read_only_root_filesystem": (
                security_context.read_only_root_filesystem
                if security_context is not None
                else None
            ),
            "run_as_non_root": (
                security_context.run_as_non_root
                if security_context is not None
                else None
            ),
            "run_as_user": (
                security_context.run_as_user if security_context is not None else None
            ),
        },
    })


def _without_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_none(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, list):
        return [_without_none(item) for item in value]
    return value


def summarize_pod(pod: V1Pod) -> dict[str, Any]:
    metadata = pod.metadata
    spec = pod.spec
    status = pod.status
    host_paths = []
    if spec is not None:
        for volume in spec.volumes or []:
            if volume.host_path is not None:
                host_paths.append(
                    {
                        "volume_name": volume.name,
                        "path": volume.host_path.path,
                        "type": volume.host_path.type,
                    }
                )
    return _without_none({
        "namespace": metadata.namespace if metadata else None,
        "name": metadata.name if metadata else None,
        "service_account": spec.service_account_name if spec else None,
        "node_name": spec.node_name if spec else None,
        "owner_references": [
            {
                "kind": owner.kind,
                "name": owner.name,
                "controller": owner.controller,
            }
            for owner in (metadata.owner_references or [])
        ]
        if metadata
        else [],
        "host_network": spec.host_network if spec else None,
        "host_pid": spec.host_pid if spec else None,
        "host_ipc": spec.host_ipc if spec else None,
        "phase": status.phase if status else None,
        "containers": [_container_summary(item) for item in (spec.containers or [])]
        if spec
        else [],
        "init_containers": [
            _container_summary(item) for item in (spec.init_containers or [])
        ]
        if spec
        else [],
        "ephemeral_containers": [
            _container_summary(item) for item in (spec.ephemeral_containers or [])
        ]
        if spec
        else [],
        "host_path_volumes": host_paths,
    })


class KubernetesReader:
    def __init__(self, api: client.CoreV1Api) -> None:
        self.api = api

    def get_pod_details(self, namespace: object, pod_name: object) -> dict[str, Any]:
        valid_namespace, valid_name = validate_pod_reference(
            namespace=namespace,
            pod_name=pod_name,
        )
        pod = self.api.read_namespaced_pod(
            name=valid_name, namespace=valid_namespace
        )
        return summarize_pod(pod)

    def get_namespace_pods(self, namespace: object) -> dict[str, Any]:
        valid_namespace = validate_namespace(namespace)
        pod_list = self.api.list_namespaced_pod(namespace=valid_namespace)
        pods = []
        for pod in pod_list.items:
            metadata = pod.metadata
            spec = pod.spec
            privileged = [
                {"name": item.name, "container_type": container_type}
                for container_type, item in iter_container_groups(pod)
                if item.security_context is not None
                and item.security_context.privileged is True
            ]
            pods.append(
                {
                    "name": metadata.name if metadata else None,
                    "phase": pod.status.phase if pod.status else None,
                    "privileged_containers": privileged,
                }
            )
        pods.sort(
            key=lambda item: (
                not bool(item["privileged_containers"]),
                item["name"] or "",
            )
        )
        returned_pods = pods[:MAX_NAMESPACE_PODS]
        return {
            "namespace": valid_namespace,
            "total_count": len(pods),
            "returned_count": len(returned_pods),
            "truncated": len(pods) > len(returned_pods),
            "pods": returned_pods,
        }
