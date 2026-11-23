import json
from types import SimpleNamespace

from agent.kube import KubernetesReader
from agent.tools import ToolExecutor


class FakeReader:
    def get_pod_details(self, namespace: object, pod_name: object) -> dict:
        return {"namespace": namespace, "name": pod_name}

    def get_namespace_pods(self, namespace: object) -> dict:
        return {"namespace": namespace, "pods": []}


def test_allows_valid_cluster_namespace() -> None:
    result = json.loads(
        ToolExecutor(FakeReader()).execute(
            "get_namespace_pods", '{"namespace":"kube-system"}'
        )
    )

    assert result == {
        "ok": True,
        "result": {"namespace": "kube-system", "pods": []},
    }


def test_rejects_invalid_namespace() -> None:
    reader = KubernetesReader(SimpleNamespace())
    result = json.loads(
        ToolExecutor(reader).execute(
            "get_namespace_pods", '{"namespace":"../../kube-system"}'
        )
    )

    assert result["ok"] is False
    assert "DNS label" in result["error"]


def test_rejects_unknown_arguments() -> None:
    result = json.loads(
        ToolExecutor(FakeReader()).execute(
            "get_pod_details",
            '{"namespace":"ai-lab","pod_name":"risky-pod","extra":true}',
        )
    )

    assert result["ok"] is False


def test_rejects_unknown_tool() -> None:
    result = json.loads(ToolExecutor(FakeReader()).execute("run_shell", "{}"))

    assert result == {"ok": False, "error": "unknown tool: run_shell"}
