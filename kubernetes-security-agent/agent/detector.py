from __future__ import annotations

import hashlib
import json
from typing import Any

from kubernetes.client import V1Container, V1EphemeralContainer, V1Pod

from .kube import iter_container_groups
from .models import SecurityFinding, WorkloadIdentity


PRIVILEGED_REASON = "container securityContext.privileged is true"


def has_privileged_container(pod: V1Pod) -> bool:
    return any(
        container.security_context is not None
        and container.security_context.privileged is True
        for _, container in iter_container_groups(pod)
    )


def _host_path_context(pod: V1Pod) -> list[dict[str, Any]]:
    if pod.spec is None:
        return []
    result = []
    for volume in pod.spec.volumes or []:
        if volume.host_path is not None:
            result.append(
                {
                    "volume_name": volume.name,
                    "host_path": volume.host_path.path,
                    "type": volume.host_path.type,
                }
            )
    return result


def _pod_workload(pod: V1Pod) -> WorkloadIdentity:
    metadata = pod.metadata
    assert metadata is not None
    owner = next(
        (item for item in metadata.owner_references or [] if item.controller),
        None,
    )
    if owner is None:
        return WorkloadIdentity(
            api_version="v1",
            kind="Pod",
            namespace=metadata.namespace,
            name=metadata.name,
            uid=str(metadata.uid),
        )
    return WorkloadIdentity(
        api_version=owner.api_version,
        kind=owner.kind,
        namespace=metadata.namespace,
        name=owner.name,
        uid=str(owner.uid),
    )


def _security_context(container: V1Container | V1EphemeralContainer) -> dict[str, Any]:
    context = container.security_context
    capabilities = context.capabilities if context is not None else None
    return {
        "privileged": context.privileged if context is not None else None,
        "allow_privilege_escalation": (
            context.allow_privilege_escalation if context is not None else None
        ),
        "read_only_root_filesystem": (
            context.read_only_root_filesystem if context is not None else None
        ),
        "run_as_non_root": context.run_as_non_root if context is not None else None,
        "run_as_user": context.run_as_user if context is not None else None,
        "run_as_group": context.run_as_group if context is not None else None,
        "capabilities": {
            "add": sorted(capabilities.add or []),
            "drop": sorted(capabilities.drop or []),
        }
        if capabilities is not None
        else None,
    }


def _finding_fingerprint(
    pod: V1Pod,
    workload: WorkloadIdentity,
    container: V1Container | V1EphemeralContainer,
    container_type: str,
    host_paths: list[dict[str, Any]],
) -> str:
    spec = pod.spec
    material = {
        "workload": {
            "api_version": workload.api_version,
            "kind": workload.kind,
            "namespace": workload.namespace,
            "name": workload.name,
            "uid": workload.uid,
        },
        "container_name": container.name,
        "container_type": container_type,
        "image": container.image,
        "security_context": _security_context(container),
        "service_account": spec.service_account_name if spec else None,
        "host_network": spec.host_network if spec else None,
        "host_pid": spec.host_pid if spec else None,
        "host_ipc": spec.host_ipc if spec else None,
        "host_path_volumes": host_paths,
    }
    encoded = json.dumps(material, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def detect_privileged_containers(
    pod: V1Pod,
    workload: WorkloadIdentity | None = None,
) -> list[SecurityFinding]:
    metadata = pod.metadata
    if metadata is None or not metadata.namespace or not metadata.name or not metadata.uid:
        return []

    host_paths = _host_path_context(pod)
    resolved_workload = workload or _pod_workload(pod)
    findings = []
    for container_type, container in iter_container_groups(pod):
        context = container.security_context
        if context is None or context.privileged is not True:
            continue
        findings.append(
            SecurityFinding(
                namespace=metadata.namespace,
                pod_name=metadata.name,
                pod_uid=str(metadata.uid),
                container_name=container.name,
                detection_reason=PRIVILEGED_REASON,
                relevant_security_configuration={
                    "container_type": container_type,
                    "privileged": True,
                    "host_path_volumes": host_paths,
                },
                workload=resolved_workload,
                fingerprint=_finding_fingerprint(
                    pod,
                    resolved_workload,
                    container,
                    container_type,
                    host_paths,
                ),
            )
        )
    return findings
