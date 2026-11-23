from __future__ import annotations

import json
import logging
from typing import Any

from kubernetes.client.exceptions import ApiException

from .kube import KubernetesReader


LOGGER = logging.getLogger(__name__)

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "get_pod_details",
        "description": (
            "Return a concise, read-only security summary for one Pod in the "
            "cluster. Environment variables and secret data are omitted."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string"},
                "pod_name": {"type": "string"},
            },
            "required": ["namespace", "pod_name"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_namespace_pods",
        "description": (
            "Return concise metadata for at most 50 Pods in one cluster namespace, "
            "prioritizing privileged Pods and reporting truncation."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"namespace": {"type": "string"}},
            "required": ["namespace"],
            "additionalProperties": False,
        },
    },
]


class ToolExecutor:
    def __init__(self, reader: KubernetesReader) -> None:
        self.reader = reader

    def execute(self, name: str, arguments_json: str) -> str:
        try:
            arguments = json.loads(arguments_json)
            if not isinstance(arguments, dict):
                raise ValueError("tool arguments must be a JSON object")
            if name == "get_pod_details":
                result = self.reader.get_pod_details(**arguments)
            elif name == "get_namespace_pods":
                result = self.reader.get_namespace_pods(**arguments)
            else:
                raise ValueError(f"unknown tool: {name}")
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            LOGGER.warning(
                "Tool input rejected",
                extra={"tool_name": name, "tool_result": "rejected"},
            )
            return json.dumps(
                {"ok": False, "error": str(exc)}, separators=(",", ":")
            )
        except ApiException as exc:
            LOGGER.warning(
                "Kubernetes tool request failed",
                extra={
                    "tool_name": name,
                    "tool_result": "kubernetes_api_error",
                    "status_code": exc.status,
                },
            )
            return json.dumps(
                {
                    "ok": False,
                    "error": "Kubernetes API request failed",
                    "status_code": exc.status,
                },
                separators=(",", ":"),
            )

        LOGGER.info(
            "Tool execution completed",
            extra={"tool_name": name, "tool_result": "success"},
        )
        return json.dumps(
            {"ok": True, "result": result},
            separators=(",", ":"),
            sort_keys=True,
        )
