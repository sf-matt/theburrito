from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


class JsonFormatter(logging.Formatter):
    _standard_fields = set(logging.makeLogRecord({}).__dict__)

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in self._standard_fields and key not in {"message", "asctime"}:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, sort_keys=True)


def configure_logging() -> None:
    log_file = os.getenv("AGENT_LOG_FILE", "").strip()
    if log_file:
        max_bytes = _positive_int("AGENT_LOG_MAX_BYTES", 5 * 1024 * 1024)
        backup_count = _positive_int("AGENT_LOG_BACKUP_COUNT", 3)
        path = Path(log_file).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = RotatingFileHandler(
            path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
    else:
        handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    for existing_handler in root.handlers[:]:
        root.removeHandler(existing_handler)
        existing_handler.close()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be at least 1")
    return value
