from kubernetes.client import (
    V1Container,
    V1ContainerStatus,
    V1EphemeralContainer,
    V1HostPathVolumeSource,
    V1ObjectMeta,
    V1OwnerReference,
    V1Pod,
    V1PodSpec,
    V1PodStatus,
    V1SecurityContext,
    V1Volume,
)

from agent.detector import PRIVILEGED_REASON, detect_privileged_containers


def make_pod(containers: list[V1Container]) -> V1Pod:
    return V1Pod(
        metadata=V1ObjectMeta(name="test-pod", namespace="ai-lab", uid="uid-1"),
        spec=V1PodSpec(containers=containers),
    )


def test_detects_privileged_container() -> None:
    pod = make_pod(
        [
            V1Container(
                name="risky",
                image="example.invalid/risky:1",
                security_context=V1SecurityContext(privileged=True),
            )
        ]
    )
    pod.spec.volumes = [
        V1Volume(
            name="host",
            host_path=V1HostPathVolumeSource(path="/var/log", type="Directory"),
        )
    ]

    findings = detect_privileged_containers(pod)

    assert len(findings) == 1
    assert findings[0].container_name == "risky"
    assert findings[0].detection_reason == PRIVILEGED_REASON
    assert findings[0].relevant_security_configuration["host_path_volumes"] == [
        {"volume_name": "host", "host_path": "/var/log", "type": "Directory"}
    ]


def test_ignores_nonprivileged_container() -> None:
    pod = make_pod(
        [
            V1Container(
                name="ordinary",
                image="example.invalid/ordinary:1",
                security_context=V1SecurityContext(privileged=False),
            )
        ]
    )

    assert detect_privileged_containers(pod) == []


def test_reports_only_privileged_containers_in_multi_container_pod() -> None:
    pod = make_pod(
        [
            V1Container(
                name="ordinary",
                image="example.invalid/ordinary:1",
                security_context=V1SecurityContext(privileged=False),
            ),
            V1Container(
                name="risky-one",
                image="example.invalid/risky:1",
                security_context=V1SecurityContext(privileged=True),
            ),
            V1Container(
                name="risky-two",
                image="example.invalid/risky:1",
                security_context=V1SecurityContext(privileged=True),
            ),
        ]
    )

    findings = detect_privileged_containers(pod)

    assert [finding.container_name for finding in findings] == [
        "risky-one",
        "risky-two",
    ]


def test_detects_privileged_init_and_ephemeral_containers() -> None:
    pod = make_pod([V1Container(name="app", image="example.invalid/app:1")])
    pod.spec.init_containers = [
        V1Container(
            name="init-risky",
            image="example.invalid/init:1",
            security_context=V1SecurityContext(privileged=True),
        )
    ]
    pod.spec.ephemeral_containers = [
        V1EphemeralContainer(
            name="debug-risky",
            image="example.invalid/debug:1",
            security_context=V1SecurityContext(privileged=True),
        )
    ]

    findings = detect_privileged_containers(pod)

    assert [
        (
            finding.container_name,
            finding.relevant_security_configuration["container_type"],
        )
        for finding in findings
    ] == [
        ("init-risky", "initContainer"),
        ("debug-risky", "ephemeralContainer"),
    ]


def test_workload_fingerprint_survives_pod_replacement_and_changes_with_image() -> None:
    owner = V1OwnerReference(
        api_version="apps/v1",
        kind="DaemonSet",
        name="node-agent",
        uid="daemonset-uid",
        controller=True,
    )

    def owned_pod(uid: str, image: str) -> V1Pod:
        return V1Pod(
            metadata=V1ObjectMeta(
                name=f"node-agent-{uid}",
                namespace="kube-system",
                uid=uid,
                owner_references=[owner],
            ),
            spec=V1PodSpec(
                containers=[
                    V1Container(
                        name="agent",
                        image=image,
                        security_context=V1SecurityContext(privileged=True),
                    )
                ]
            ),
        )

    first = detect_privileged_containers(owned_pod("pod-1", "agent:v1"))[0]
    replacement = detect_privileged_containers(owned_pod("pod-2", "agent:v1"))[0]
    changed = detect_privileged_containers(owned_pod("pod-3", "agent:v2"))[0]

    assert first.workload.kind == "DaemonSet"
    assert first.fingerprint == replacement.fingerprint
    assert first.fingerprint != changed.fingerprint


def test_fingerprint_ignores_runtime_image_id_startup_transitions() -> None:
    def pod_with_image_id(image_id: str | None) -> V1Pod:
        pod = make_pod(
            [
                V1Container(
                    name="risky",
                    image="example.invalid/risky:1",
                    security_context=V1SecurityContext(privileged=True),
                )
            ]
        )
        if image_id is not None:
            pod.status = V1PodStatus(
                container_statuses=[
                    V1ContainerStatus(
                        name="risky",
                        image="example.invalid/risky:1",
                        image_id=image_id,
                        ready=image_id != "",
                        restart_count=0,
                    )
                ]
            )
        return pod

    without_status = detect_privileged_containers(pod_with_image_id(None))[0]
    before_image_resolution = detect_privileged_containers(pod_with_image_id(""))[0]
    after_image_resolution = detect_privileged_containers(
        pod_with_image_id("containerd://sha256:resolved")
    )[0]

    assert without_status.fingerprint == before_image_resolution.fingerprint
    assert without_status.fingerprint == after_image_resolution.fingerprint
