from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable

from .models import SecurityAssessment, SecurityFinding


class InvestigationStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    OBSERVED = "observed"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class InvestigationRecord:
    record_id: str
    cluster_id: str
    workload: dict[str, str]
    container_name: str
    detection_reason: str
    fingerprint: str
    status: InvestigationStatus
    first_seen: float
    last_seen: float
    updated_at: float
    observation_count: int
    last_pod_name: str
    last_persisted_observation: float
    assessment: dict[str, Any] | None = None
    acknowledged: bool = False
    acknowledged_reason: str | None = None
    acknowledged_at: float | None = None
    review_after: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InvestigationRecord":
        return cls(
            record_id=str(data["record_id"]),
            cluster_id=str(data["cluster_id"]),
            workload=dict(data["workload"]),
            container_name=str(data["container_name"]),
            detection_reason=str(data["detection_reason"]),
            fingerprint=str(data["fingerprint"]),
            status=InvestigationStatus(data["status"]),
            first_seen=float(data["first_seen"]),
            last_seen=float(data["last_seen"]),
            updated_at=float(data["updated_at"]),
            observation_count=int(data["observation_count"]),
            last_pod_name=str(data["last_pod_name"]),
            last_persisted_observation=float(
                data.get("last_persisted_observation", data["last_seen"])
            ),
            assessment=data.get("assessment"),
            acknowledged=bool(data.get("acknowledged", False)),
            acknowledged_reason=data.get("acknowledged_reason"),
            acknowledged_at=data.get("acknowledged_at"),
            review_after=data.get("review_after"),
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        return result


class InvestigationRegistry:
    def __init__(
        self,
        cooldown_seconds: int,
        state_file: str | Path | None = None,
        cluster_id: str = "local-test-cluster",
        observation_flush_seconds: int = 60,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if observation_flush_seconds < 0:
            raise ValueError("observation flush interval must not be negative")
        self._cooldown_seconds = cooldown_seconds
        self._state_file = Path(state_file).expanduser().resolve() if state_file else None
        self._cluster_id = cluster_id
        self._observation_flush_seconds = observation_flush_seconds
        self._clock = clock
        self._records: dict[str, InvestigationRecord] = {}
        self._state_mtime_ns: int | None = None
        self._lock = threading.Lock()
        with self._state_guard():
            pass

    def begin(self, finding: SecurityFinding, *, observation_only: bool = False) -> bool:
        now = self._clock()
        record_id = self._record_id(finding)
        with self._lock, self._state_guard():
            record = self._records.get(record_id)
            if record is not None:
                record.last_seen = now
                record.last_pod_name = finding.pod_name
                record.observation_count += 1

                if record.acknowledged:
                    if record.review_after is None or now < record.review_after:
                        self._save_observation_if_due(record, now)
                        return False
                    record.acknowledged = False
                    record.acknowledged_reason = None
                    record.acknowledged_at = None
                    record.review_after = None
                    record.status = InvestigationStatus.FAILED
                    record.updated_at = 0

                if record.status == InvestigationStatus.COMPLETED:
                    self._save_observation_if_due(record, now)
                    return False
                if record.status == InvestigationStatus.OBSERVED and observation_only:
                    self._save_observation_if_due(record, now)
                    return False
                if (
                    record.status
                    in {InvestigationStatus.IN_PROGRESS, InvestigationStatus.FAILED}
                    and now - record.updated_at < self._cooldown_seconds
                ):
                    self._save_observation_if_due(record, now)
                    return False

                record.status = InvestigationStatus.IN_PROGRESS
                record.updated_at = now
                self._save()
                return True

            self._records[record_id] = InvestigationRecord(
                record_id=record_id,
                cluster_id=self._cluster_id,
                workload=asdict(finding.workload),
                container_name=finding.container_name,
                detection_reason=finding.detection_reason,
                fingerprint=finding.fingerprint,
                status=InvestigationStatus.IN_PROGRESS,
                first_seen=now,
                last_seen=now,
                updated_at=now,
                observation_count=1,
                last_pod_name=finding.pod_name,
                last_persisted_observation=now,
            )
            self._save()
            return True

    def complete(
        self,
        finding: SecurityFinding,
        assessment: SecurityAssessment | None = None,
    ) -> None:
        status = (
            InvestigationStatus.COMPLETED
            if assessment is not None
            else InvestigationStatus.OBSERVED
        )
        with self._lock, self._state_guard():
            record = self._require_record(finding)
            record.status = status
            record.updated_at = self._clock()
            record.assessment = assessment.to_dict() if assessment is not None else None
            self._save()

    def fail(self, finding: SecurityFinding) -> None:
        with self._lock, self._state_guard():
            record = self._require_record(finding)
            record.status = InvestigationStatus.FAILED
            record.updated_at = self._clock()
            self._save()

    def get(self, finding: SecurityFinding) -> InvestigationRecord | None:
        with self._lock, self._state_guard():
            return self._records.get(self._record_id(finding))

    def inventory(
        self,
        disposition: str | None = None,
        *,
        acknowledged_only: bool = False,
    ) -> list[dict[str, Any]]:
        with self._lock, self._state_guard():
            records = list(self._records.values())
            if disposition is not None:
                records = [
                    record
                    for record in records
                    if record.assessment is not None
                    and record.assessment.get("disposition") == disposition
                ]
            if acknowledged_only:
                records = [record for record in records if record.acknowledged]
            records.sort(
                key=lambda item: (
                    item.workload["namespace"],
                    item.workload["kind"],
                    item.workload["name"],
                    item.container_name,
                )
            )
            return [record.to_dict() for record in records]

    def acknowledge(
        self,
        record_id_prefix: str,
        reason: str,
        review_after: float | None = None,
    ) -> InvestigationRecord:
        record_id_prefix = record_id_prefix.lower()
        if not reason.strip():
            raise ValueError("acknowledgment reason must not be empty")
        if len(record_id_prefix) < 8 or any(
            character not in "0123456789abcdef" for character in record_id_prefix.lower()
        ):
            raise ValueError("record ID prefix must contain at least 8 hexadecimal characters")
        with self._lock, self._state_guard():
            matches = [
                record
                for record_id, record in self._records.items()
                if record_id.startswith(record_id_prefix)
            ]
            if not matches:
                raise ValueError("no assessment record matches that record ID")
            if len(matches) > 1:
                raise ValueError("record ID prefix is ambiguous")
            record = matches[0]
            if record.status not in {
                InvestigationStatus.OBSERVED,
                InvestigationStatus.COMPLETED,
            }:
                raise ValueError("only observed or completed records can be acknowledged")
            record.acknowledged = True
            record.acknowledged_reason = reason.strip()
            record.acknowledged_at = self._clock()
            record.review_after = review_after
            self._save()
            return record

    @property
    def size(self) -> int:
        with self._lock, self._state_guard():
            return len(self._records)

    def _record_id(self, finding: SecurityFinding) -> str:
        material = json.dumps(
            [self._cluster_id, *finding.key],
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(material).hexdigest()

    def _require_record(self, finding: SecurityFinding) -> InvestigationRecord:
        record = self._records.get(self._record_id(finding))
        if record is None:
            raise RuntimeError("investigation record does not exist")
        return record

    def _load_from_disk(self) -> None:
        if self._state_file is None:
            return
        if not self._state_file.exists():
            if self._state_mtime_ns is not None:
                self._records = {}
                self._state_mtime_ns = None
            return
        state_mtime_ns = self._state_file.stat().st_mtime_ns
        if state_mtime_ns == self._state_mtime_ns:
            return
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
            if data.get("version") != 1 or not isinstance(data.get("records"), list):
                raise ValueError("unsupported state file format")
            records = [InvestigationRecord.from_dict(item) for item in data["records"]]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not load agent state: {exc}") from exc
        self._records = {record.record_id: record for record in records}
        os.chmod(self._state_file, 0o600)
        self._state_mtime_ns = state_mtime_ns

    @contextmanager
    def _state_guard(self):
        if self._state_file is None:
            yield
            return
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        lock_path = Path(f"{self._state_file}.lock")
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            os.chmod(lock_path, 0o600)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            self._load_from_disk()
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _save(self) -> None:
        if self._state_file is None:
            return
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        persisted_at = self._clock()
        for record in self._records.values():
            record.last_persisted_observation = persisted_at
        payload = {
            "version": 1,
            "records": [record.to_dict() for record in self._records.values()],
        }
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._state_file.parent,
                prefix=f".{self._state_file.name}.",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, self._state_file)
            self._state_mtime_ns = self._state_file.stat().st_mtime_ns
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    def _save_observation_if_due(
        self,
        record: InvestigationRecord,
        now: float,
    ) -> None:
        if (
            self._observation_flush_seconds == 0
            or now - record.last_persisted_observation
            >= self._observation_flush_seconds
        ):
            self._save()
