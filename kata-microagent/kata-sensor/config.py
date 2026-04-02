import os

POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "2"))
HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", "15"))
RECEIVER_URL = os.environ.get("RECEIVER_URL", "").strip()
POD_NAME = os.environ.get("POD_NAME", "unknown")
POD_NAMESPACE = os.environ.get("POD_NAMESPACE", "unknown")
MODE = os.environ.get("MODE", "kata")
EXPECTED_PROCESSES = {
    p.strip() for p in os.environ.get("EXPECTED_PROCESSES", "sleep").split(",") if p.strip()
}