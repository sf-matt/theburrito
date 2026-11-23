from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


@dataclass(frozen=True)
class WorkloadIdentity:
    api_version: str
    kind: str
    namespace: str
    name: str
    uid: str


@dataclass(frozen=True)
class SecurityFinding:
    namespace: str
    pod_name: str
    pod_uid: str
    container_name: str
    detection_reason: str
    relevant_security_configuration: dict[str, Any]
    workload: WorkloadIdentity
    fingerprint: str

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (
            self.workload.uid,
            self.container_name,
            self.detection_reason,
            self.fingerprint,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_prompt_dict(self) -> dict[str, Any]:
        """Return only evidence the model needs, excluding registry identifiers."""
        return {
            "namespace": self.namespace,
            "pod_name": self.pod_name,
            "container_name": self.container_name,
            "detection_reason": self.detection_reason,
            "relevant_security_configuration": self.relevant_security_configuration,
            "workload": {
                "kind": self.workload.kind,
                "namespace": self.workload.namespace,
                "name": self.workload.name,
            },
        }


class AssessmentDisposition(StrEnum):
    EXPECTED_SYSTEM_COMPONENT = "expected_system_component"
    REVIEW_WARRANTED = "review_warranted"
    LIKELY_ACCEPTABLE = "likely_acceptable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class SecurityAssessment:
    disposition: AssessmentDisposition
    summary: str
    observed_concern: str
    supporting_evidence: list[str]
    potential_implications: list[str]
    recommended_next_steps: list[str]
    uncertainties: list[str]

    @classmethod
    def from_json(cls, value: str) -> "SecurityAssessment":
        data = json.loads(value)
        if not isinstance(data, dict):
            raise ValueError("assessment must be a JSON object")
        required = {
            "disposition",
            "summary",
            "observed_concern",
            "supporting_evidence",
            "potential_implications",
            "recommended_next_steps",
            "uncertainties",
        }
        if set(data) != required:
            raise ValueError("assessment fields do not match the required schema")
        for field_name in required - {"disposition"}:
            field_value = data[field_name]
            expected_type = str if field_name in {"summary", "observed_concern"} else list
            if not isinstance(field_value, expected_type):
                raise ValueError(f"assessment field {field_name} has the wrong type")
            if isinstance(field_value, list) and not all(
                isinstance(item, str) for item in field_value
            ):
                raise ValueError(f"assessment field {field_name} must contain strings")
        return cls(
            disposition=AssessmentDisposition(data["disposition"]),
            summary=data["summary"],
            observed_concern=data["observed_concern"],
            supporting_evidence=data["supporting_evidence"],
            potential_implications=data["potential_implications"],
            recommended_next_steps=data["recommended_next_steps"],
            uncertainties=data["uncertainties"],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
