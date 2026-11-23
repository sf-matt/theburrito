import json
import stat

from agent.models import (
    AssessmentDisposition,
    SecurityAssessment,
    SecurityFinding,
    WorkloadIdentity,
)
from agent.registry import InvestigationRegistry, InvestigationStatus


def make_finding(
    *,
    pod_uid: str = "pod-uid-1",
    workload_uid: str = "workload-uid-1",
    fingerprint: str = "fingerprint-1",
) -> SecurityFinding:
    return SecurityFinding(
        namespace="ai-lab",
        pod_name=f"risky-{pod_uid}",
        pod_uid=pod_uid,
        container_name="risky",
        detection_reason="privileged",
        relevant_security_configuration={"privileged": True},
        workload=WorkloadIdentity(
            api_version="apps/v1",
            kind="DaemonSet",
            namespace="ai-lab",
            name="risky-workload",
            uid=workload_uid,
        ),
        fingerprint=fingerprint,
    )


def assessment() -> SecurityAssessment:
    return SecurityAssessment(
        disposition=AssessmentDisposition.EXPECTED_SYSTEM_COMPONENT,
        summary="Expected node component",
        observed_concern="Container is privileged",
        supporting_evidence=["DaemonSet owner"],
        potential_implications=["Host-level access"],
        recommended_next_steps=["Review after upgrades"],
        uncertainties=[],
    )


def test_duplicate_workload_pods_are_not_started_twice() -> None:
    registry = InvestigationRegistry(cooldown_seconds=60, clock=lambda: 10.0)
    first = make_finding(pod_uid="pod-1")
    replacement = make_finding(pod_uid="pod-2")

    assert registry.begin(first) is True
    assert registry.begin(replacement) is False
    assert registry.get(first).status == InvestigationStatus.IN_PROGRESS
    assert registry.get(first).observation_count == 2


def test_completed_fingerprint_remains_suppressed_after_cooldown() -> None:
    now = [10.0]
    registry = InvestigationRegistry(cooldown_seconds=60, clock=lambda: now[0])
    finding = make_finding()

    assert registry.begin(finding) is True
    registry.complete(finding, assessment())
    now[0] = 1_000.0

    assert registry.begin(finding) is False
    assert registry.get(finding).status == InvestigationStatus.COMPLETED


def test_changed_fingerprint_creates_new_investigation() -> None:
    registry = InvestigationRegistry(cooldown_seconds=60, clock=lambda: 10.0)
    original = make_finding(fingerprint="fingerprint-1")
    changed = make_finding(fingerprint="fingerprint-2")

    registry.begin(original)
    registry.complete(original, assessment())

    assert registry.begin(changed) is True
    assert registry.size == 2


def test_dry_run_observation_can_be_investigated_later() -> None:
    registry = InvestigationRegistry(cooldown_seconds=60, clock=lambda: 10.0)
    finding = make_finding()

    assert registry.begin(finding, observation_only=True) is True
    registry.complete(finding)
    assert registry.begin(finding, observation_only=True) is False
    assert registry.begin(finding, observation_only=False) is True


def test_completed_state_survives_restart(tmp_path) -> None:
    state_file = tmp_path / "assessments.json"
    finding = make_finding()
    first = InvestigationRegistry(
        cooldown_seconds=60,
        state_file=state_file,
        cluster_id="cluster-a",
        clock=lambda: 10.0,
    )
    first.begin(finding)
    first.complete(finding, assessment())

    second = InvestigationRegistry(
        cooldown_seconds=60,
        state_file=state_file,
        cluster_id="cluster-a",
        clock=lambda: 1_000.0,
    )

    assert second.begin(finding) is False
    assert second.inventory()[0]["assessment"]["disposition"] == (
        "expected_system_component"
    )
    assert stat.S_IMODE(state_file.stat().st_mode) == 0o600
    assert json.loads(state_file.read_text())["version"] == 1


def test_duplicate_observation_writes_are_coalesced(tmp_path) -> None:
    now = [10.0]
    state_file = tmp_path / "assessments.json"
    finding = make_finding()
    registry = InvestigationRegistry(
        cooldown_seconds=60,
        state_file=state_file,
        cluster_id="cluster-a",
        observation_flush_seconds=60,
        clock=lambda: now[0],
    )
    registry.begin(finding)
    registry.complete(finding, assessment())
    initial_contents = state_file.read_text()

    now[0] = 20.0
    assert registry.begin(finding) is False
    assert state_file.read_text() == initial_contents

    now[0] = 70.0
    assert registry.begin(finding) is False
    persisted = json.loads(state_file.read_text())["records"][0]
    assert persisted["last_seen"] == 70.0
    assert persisted["observation_count"] == 3


def test_acknowledgment_expires_and_reopens_record() -> None:
    now = [10.0]
    registry = InvestigationRegistry(cooldown_seconds=60, clock=lambda: now[0])
    finding = make_finding()
    registry.begin(finding)
    registry.complete(finding, assessment())
    record_id = registry.inventory()[0]["record_id"]
    registry.acknowledge(record_id[:12], "Reviewed system component", 100.0)

    now[0] = 99.0
    assert registry.begin(finding) is False
    now[0] = 100.0
    assert registry.begin(finding) is True
    assert registry.get(finding).acknowledged is False


def test_running_registry_reloads_acknowledgment_written_by_cli_process(tmp_path) -> None:
    state_file = tmp_path / "assessments.json"
    finding = make_finding()
    running = InvestigationRegistry(
        cooldown_seconds=60,
        state_file=state_file,
        cluster_id="cluster-a",
        clock=lambda: 10.0,
    )
    running.begin(finding)
    running.complete(finding, assessment())

    management = InvestigationRegistry(
        cooldown_seconds=60,
        state_file=state_file,
        cluster_id="inventory-only",
        clock=lambda: 20.0,
    )
    record_id = management.inventory()[0]["record_id"]
    management.acknowledge(record_id[:12], "Reviewed through CLI")

    assert running.inventory(acknowledged_only=True)[0]["acknowledged_reason"] == (
        "Reviewed through CLI"
    )


def test_failed_record_retries_only_after_cooldown() -> None:
    now = [10.0]
    registry = InvestigationRegistry(cooldown_seconds=60, clock=lambda: now[0])
    finding = make_finding()
    registry.begin(finding)
    registry.fail(finding)

    now[0] = 69.0
    assert registry.begin(finding) is False
    now[0] = 70.0
    assert registry.begin(finding) is True
