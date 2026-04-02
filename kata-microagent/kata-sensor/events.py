import json
from datetime import datetime, timezone

import requests

from config import MODE, POD_NAME, POD_NAMESPACE, RECEIVER_URL


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit_event(event: dict) -> None:
    print(json.dumps(event), flush=True)

    if RECEIVER_URL:
        try:
            resp = requests.post(RECEIVER_URL, json=event, timeout=3)
            resp.raise_for_status()
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "ts": utc_now(),
                        "source": "kata-sensor",
                        "event_type": "send_failed",
                        "severity": "medium",
                        "error": str(exc),
                        "pod": POD_NAME,
                        "namespace": POD_NAMESPACE,
                        "mode": MODE,
                    }
                ),
                flush=True,
            )


def base_event() -> dict:
    return {
        "source": "kata-sensor",
        "pod": POD_NAME,
        "namespace": POD_NAMESPACE,
        "mode": MODE,
    }