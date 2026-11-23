from types import SimpleNamespace

from kubernetes import client, config
from kubernetes.client import (
    V1Container,
    V1EphemeralContainer,
    V1ObjectMeta,
    V1OwnerReference,
    V1Pod,
    V1PodSpec,
    V1SecurityContext,
)

from agent.kube import (
    MAX_NAMESPACE_PODS,
    KubernetesReader,
    WorkloadResolver,
    load_core_api,
    summarize_pod,
)


def make_mixed_pod() -> V1Pod:
    return V1Pod(
        metadata=V1ObjectMeta(
            name="mixed",
            namespace="ai-lab",
            uid="uid-1",
            owner_references=[
                V1OwnerReference(
                    api_version="apps/v1",
                    kind="DaemonSet",
                    name="node-helper",
                    uid="owner-1",
                    controller=True,
                )
            ],
        ),
        spec=V1PodSpec(
            containers=[V1Container(name="app", image="example.invalid/app:1")],
            init_containers=[
                V1Container(
                    name="init-risky",
                    image="example.invalid/init:1",
                    security_context=V1SecurityContext(privileged=True),
                )
            ],
            ephemeral_containers=[
                V1EphemeralContainer(
                    name="debug-risky",
                    image="example.invalid/debug:1",
                    security_context=V1SecurityContext(privileged=True),
                )
            ],
        ),
    )


def test_summaries_include_init_and_ephemeral_container_evidence() -> None:
    pod = make_mixed_pod()
    summary = summarize_pod(pod)
    api = SimpleNamespace(
        list_namespaced_pod=lambda namespace: SimpleNamespace(items=[pod])
    )
    namespace_summary = KubernetesReader(api).get_namespace_pods("ai-lab")

    assert summary["init_containers"][0]["name"] == "init-risky"
    assert summary["ephemeral_containers"][0]["name"] == "debug-risky"
    assert summary["owner_references"] == [
        {"kind": "DaemonSet", "name": "node-helper", "controller": True}
    ]
    assert "uid" not in summary
    assert summary["containers"][0]["security_context"] == {}
    assert namespace_summary["pods"][0]["privileged_containers"] == [
        {"name": "init-risky", "container_type": "initContainer"},
        {"name": "debug-risky", "container_type": "ephemeralContainer"},
    ]


def test_kubeconfig_loading_disables_credential_persistence(monkeypatch) -> None:
    active_context = {
        "name": "ai-investigator-context",
        "context": {"cluster": "lab", "user": "ai-investigator"},
    }
    monkeypatch.setattr(
        config,
        "list_kube_config_contexts",
        lambda config_file: ([active_context], active_context),
    )
    calls = {}

    def fake_load_kube_config(**kwargs) -> None:
        calls.update(kwargs)
        kwargs["client_configuration"].host = "https://192.0.2.10:6443"

    monkeypatch.setattr(config, "load_kube_config", fake_load_kube_config)
    api_client = object()
    monkeypatch.setattr(client, "ApiClient", lambda configuration: api_client)
    monkeypatch.setattr(client, "CoreV1Api", lambda value: value)

    result = load_core_api("/tmp/ai-investigator.kubeconfig")

    assert result is api_client
    assert calls["persist_config"] is False
    assert calls["config_file"] == "/tmp/ai-investigator.kubeconfig"


def test_resolves_replicaset_to_top_level_deployment() -> None:
    pod = V1Pod(
        metadata=V1ObjectMeta(
            name="web-abc",
            namespace="default",
            uid="pod-uid",
            owner_references=[
                V1OwnerReference(
                    api_version="apps/v1",
                    kind="ReplicaSet",
                    name="web-abc",
                    uid="replicaset-uid",
                    controller=True,
                )
            ],
        ),
        spec=V1PodSpec(containers=[V1Container(name="web", image="web:v1")]),
    )
    replica_set = SimpleNamespace(
        metadata=V1ObjectMeta(
            name="web-abc",
            namespace="default",
            uid="replicaset-uid",
            owner_references=[
                V1OwnerReference(
                    api_version="apps/v1",
                    kind="Deployment",
                    name="web",
                    uid="deployment-uid",
                    controller=True,
                )
            ],
        )
    )
    resolver = WorkloadResolver(
        apps_api=SimpleNamespace(
            read_namespaced_replica_set=lambda **kwargs: replica_set
        ),
        batch_api=SimpleNamespace(),
    )

    workload = resolver.resolve(pod)

    assert workload.kind == "Deployment"
    assert workload.name == "web"
    assert workload.uid == "deployment-uid"


def test_owner_resolution_cache_avoids_repeated_controller_reads() -> None:
    calls = []
    parent = V1OwnerReference(
        api_version="apps/v1",
        kind="Deployment",
        name="web",
        uid="deployment-uid",
        controller=True,
    )
    replica_set = SimpleNamespace(
        metadata=V1ObjectMeta(owner_references=[parent])
    )

    def read_replica_set(**kwargs):
        calls.append(kwargs)
        return replica_set

    resolver = WorkloadResolver(
        apps_api=SimpleNamespace(read_namespaced_replica_set=read_replica_set),
        batch_api=SimpleNamespace(),
        cache_size=2,
    )
    owner = V1OwnerReference(
        api_version="apps/v1",
        kind="ReplicaSet",
        name="web-abc",
        uid="replicaset-uid",
        controller=True,
    )

    def pod(uid: str) -> V1Pod:
        return V1Pod(
            metadata=V1ObjectMeta(
                name=f"web-{uid}",
                namespace="default",
                uid=uid,
                owner_references=[owner],
            ),
            spec=V1PodSpec(containers=[V1Container(name="web", image="web:v1")]),
        )

    assert resolver.resolve(pod("pod-1")).kind == "Deployment"
    assert resolver.resolve(pod("pod-2")).kind == "Deployment"
    assert len(calls) == 1


def test_resolves_job_to_top_level_cronjob() -> None:
    pod = V1Pod(
        metadata=V1ObjectMeta(
            name="scan-123",
            namespace="security",
            uid="pod-uid",
            owner_references=[
                V1OwnerReference(
                    api_version="batch/v1",
                    kind="Job",
                    name="scan-123",
                    uid="job-uid",
                    controller=True,
                )
            ],
        ),
        spec=V1PodSpec(containers=[V1Container(name="scan", image="scan:v1")]),
    )
    job = SimpleNamespace(
        metadata=V1ObjectMeta(
            name="scan-123",
            namespace="security",
            uid="job-uid",
            owner_references=[
                V1OwnerReference(
                    api_version="batch/v1",
                    kind="CronJob",
                    name="scan",
                    uid="cronjob-uid",
                    controller=True,
                )
            ],
        )
    )
    resolver = WorkloadResolver(
        apps_api=SimpleNamespace(),
        batch_api=SimpleNamespace(read_namespaced_job=lambda **kwargs: job),
    )

    workload = resolver.resolve(pod)

    assert workload.kind == "CronJob"
    assert workload.name == "scan"
    assert workload.uid == "cronjob-uid"


def test_namespace_summary_is_bounded_and_prioritizes_privileged_pods() -> None:
    pods = [
        V1Pod(
            metadata=V1ObjectMeta(
                name=f"ordinary-{index:02d}", namespace="default", uid=f"uid-{index}"
            ),
            spec=V1PodSpec(
                containers=[V1Container(name="app", image="example.invalid/app:1")]
            ),
        )
        for index in range(MAX_NAMESPACE_PODS + 5)
    ]
    pods.append(
        V1Pod(
            metadata=V1ObjectMeta(
                name="privileged-last", namespace="default", uid="uid-privileged"
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
    )
    reader = KubernetesReader(
        SimpleNamespace(
            list_namespaced_pod=lambda namespace: SimpleNamespace(items=pods)
        )
    )

    result = reader.get_namespace_pods("default")

    assert result["total_count"] == MAX_NAMESPACE_PODS + 6
    assert result["returned_count"] == MAX_NAMESPACE_PODS
    assert result["truncated"] is True
    assert result["pods"][0]["name"] == "privileged-last"
