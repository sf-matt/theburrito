from datetime import datetime, timezone
from html import escape

from flask import Flask, jsonify, request

app = Flask(__name__)
EVENTS: list[dict] = []
SENSORS: dict[str, dict] = {}

STALE_AFTER_SECONDS = 45
OFFLINE_AFTER_SECONDS = 90
MAX_EVENTS = 1000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_epoch() -> float:
    return datetime.now(timezone.utc).timestamp()


def sensor_key(namespace: str, pod: str) -> str:
    return f"{namespace}/{pod}"


def current_sensor_status(last_seen_epoch: float) -> str:
    age = utc_epoch() - last_seen_epoch
    if age >= OFFLINE_AFTER_SECONDS:
        return "offline"
    if age >= STALE_AFTER_SECONDS:
        return "stale"
    return "healthy"


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok"}), 200


@app.route("/events", methods=["POST"])
def post_event():
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "invalid JSON object"}), 400

    data["_received_at"] = utc_now()
    EVENTS.append(data)
    if len(EVENTS) > MAX_EVENTS:
        del EVENTS[:-MAX_EVENTS]

    event_type = data.get("event_type")
    namespace = data.get("namespace", "unknown")
    pod = data.get("pod", "unknown")

    if event_type in {"sensor_started", "heartbeat"}:
        key = sensor_key(namespace, pod)
        SENSORS[key] = {
            "namespace": namespace,
            "pod": pod,
            "mode": data.get("mode", ""),
            "source": data.get("source", ""),
            "last_heartbeat": data["_received_at"],
            "last_heartbeat_epoch": utc_epoch(),
        }

    print(f"Received event: {data}", flush=True)
    return jsonify({"status": "ok", "count": len(EVENTS)}), 200


@app.route("/events", methods=["GET"])
def get_events():
    return jsonify(EVENTS), 200


@app.route("/sensors", methods=["GET"])
def get_sensors():
    output = []
    for key, info in sorted(
        SENSORS.items(),
        key=lambda item: item[1]["last_heartbeat_epoch"],
        reverse=True,
    ):
        output.append(
            {
                "key": key,
                "namespace": info["namespace"],
                "pod": info["pod"],
                "mode": info["mode"],
                "source": info["source"],
                "last_heartbeat": info["last_heartbeat"],
                "status": current_sensor_status(info["last_heartbeat_epoch"]),
            }
        )
    return jsonify(output), 200


@app.route("/", methods=["GET"])
def index():
    sensor_rows = []
    for _, info in sorted(
        SENSORS.items(),
        key=lambda item: item[1]["last_heartbeat_epoch"],
        reverse=True,
    ):
        sensor_rows.append(
            "<tr>"
            f"<td>{escape(info['namespace'])}</td>"
            f"<td>{escape(info['pod'])}</td>"
            f"<td>{escape(info['mode'])}</td>"
            f"<td>{escape(current_sensor_status(info['last_heartbeat_epoch']))}</td>"
            f"<td>{escape(info['last_heartbeat'])}</td>"
            "</tr>"
        )

    event_rows = []
    for e in reversed(EVENTS[-50:]):
        event_rows.append(
            "<tr>"
            f"<td>{escape(str(e.get('_received_at', '')))}</td>"
            f"<td>{escape(str(e.get('event_type', '')))}</td>"
            f"<td>{escape(str(e.get('process', '')))}</td>"
            f"<td>{escape(str(e.get('pid', '')))}</td>"
            f"<td>{escape(str(e.get('exe_path', '')))}</td>"
            f"<td>{escape(str(e.get('cmdline', '')))}</td>"
            f"<td>{escape(str(e.get('pod', '')))}</td>"
            f"<td>{escape(str(e.get('namespace', '')))}</td>"
            f"<td>{escape(str(e.get('severity', '')))}</td>"
            f"<td>{escape(str(e.get('reason', '')))}</td>"
            "</tr>"
        )

    html = f"""
    <html>
      <head>
        <title>Kata Receiver</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 24px; }}
          table {{ border-collapse: collapse; width: 100%; margin-bottom: 32px; }}
          th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; vertical-align: top; }}
          th {{ background: #f5f5f5; }}
          td {{ word-break: break-word; }}
        </style>
      </head>
      <body>
        <h1>Kata Receiver</h1>

        <h2>Sensor Status</h2>
        <table>
          <tr>
            <th>Namespace</th>
            <th>Pod</th>
            <th>Mode</th>
            <th>Status</th>
            <th>Last Heartbeat</th>
          </tr>
          {''.join(sensor_rows)}
        </table>

        <h2>Recent Events</h2>
        <table>
          <tr>
            <th>Received</th>
            <th>Event Type</th>
            <th>Process</th>
            <th>PID</th>
            <th>Executable</th>
            <th>Command</th>
            <th>Pod</th>
            <th>Namespace</th>
            <th>Severity</th>
            <th>Reason</th>
          </tr>
          {''.join(event_rows)}
        </table>
      </body>
    </html>
    """
    return html, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)