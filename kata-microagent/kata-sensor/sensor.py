import os
import time
from pathlib import Path

from config import EXPECTED_PROCESSES, HEARTBEAT_INTERVAL, POLL_INTERVAL
from events import base_event, emit_event, utc_now
from procfs import (
    get_cmdline,
    get_exe_path,
    get_ppid,
    get_process_name,
    get_uid,
    list_pids,
)
from rules import RULES

seen_matches = set()
last_heartbeat = 0.0

EXEC_PATHS = ["/bin", "/usr/bin", "/usr/local/bin", "/sbin", "/usr/sbin"]
exec_baseline = set()


def parent_name(ppid: int | None) -> str:
    if not ppid:
        return ""
    return get_process_name(str(ppid)) or ""


def build_exec_baseline() -> set[str]:
    baseline = set()

    for root in EXEC_PATHS:
        root_path = Path(root)
        if not root_path.exists():
            continue

        for item in root_path.rglob("*"):
            try:
                if item.is_file() and os.access(item, os.X_OK):
                    baseline.add(str(item.resolve()))
            except Exception:
                continue

    return baseline


def match_rules(proc_name: str, cmdline: str):
    matches = []
    lower_cmd = cmdline.lower()

    if proc_name in EXPECTED_PROCESSES:
        return matches

    for rule in RULES:
        if proc_name not in rule["process_names"]:
            continue

        patterns = rule["cmdline_patterns"]
        if not patterns:
            matches.append((rule, "process_name", proc_name))
            continue

        for pattern in patterns:
            if pattern.lower() in lower_cmd:
                matches.append((rule, "cmdline_pattern", pattern))
                break

    return matches


def build_event(pid: str, proc_name: str, cmdline: str, rule: dict, matched_on: str, matched_value: str) -> dict:
    ppid = get_ppid(pid)
    exe_path = get_exe_path(pid)

    event = base_event()
    event.update(
        {
            "ts": utc_now(),
            "event_type": rule["event_type"],
            "severity": rule["severity"],
            "process": proc_name,
            "pid": int(pid),
            "ppid": ppid,
            "parent_process": parent_name(ppid),
            "uid": get_uid(pid),
            "cmdline": cmdline,
            "exe_path": exe_path,
            "matched_on": matched_on,
            "matched_value": matched_value,
            "reason": rule["reason"],
        }
    )
    return event


def build_post_start_binary_event(pid: str, proc_name: str, cmdline: str, exe_path: str) -> dict:
    ppid = get_ppid(pid)

    event = base_event()
    event.update(
        {
            "ts": utc_now(),
            "event_type": "post_start_binary_execution",
            "severity": "high",
            "process": proc_name,
            "pid": int(pid),
            "ppid": ppid,
            "parent_process": parent_name(ppid),
            "uid": get_uid(pid),
            "cmdline": cmdline,
            "exe_path": exe_path,
            "matched_on": "exe_path_not_in_baseline",
            "matched_value": exe_path,
            "reason": "binary executed that was not present when workload started",
        }
    )
    return event


def emit_heartbeat() -> None:
    event = base_event()
    event.update(
        {
            "ts": utc_now(),
            "event_type": "heartbeat",
            "severity": "info",
            "status": "alive",
        }
    )
    emit_event(event)


def scan_once() -> None:
    global seen_matches

    current_pids = set()

    for pid in list_pids():
        current_pids.add(pid)
        proc_name = get_process_name(pid)
        if not proc_name:
            continue

        cmdline = get_cmdline(pid)
        exe_path = get_exe_path(pid)

        # Static rule matching
        for rule, matched_on, matched_value in match_rules(proc_name, cmdline):
            key = (pid, rule["event_type"])
            if key in seen_matches:
                continue
            emit_event(build_event(pid, proc_name, cmdline, rule, matched_on, matched_value))
            seen_matches.add(key)

        # Dynamic drop-and-execute style detection
        if proc_name not in EXPECTED_PROCESSES and exe_path and exe_path not in exec_baseline:
            key = (pid, "post_start_binary_execution")
            if key not in seen_matches:
                emit_event(build_post_start_binary_event(pid, proc_name, cmdline, exe_path))
                seen_matches.add(key)

    seen_matches = {m for m in seen_matches if m[0] in current_pids}


def main() -> None:
    global last_heartbeat
    global exec_baseline

    exec_baseline = build_exec_baseline()

    started = base_event()
    started.update(
        {
            "ts": utc_now(),
            "event_type": "sensor_started",
            "severity": "info",
            "poll_interval": POLL_INTERVAL,
            "heartbeat_interval": HEARTBEAT_INTERVAL,
            "baseline_exec_count": len(exec_baseline),
        }
    )
    emit_event(started)

    while True:
        try:
            now = time.time()
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                emit_heartbeat()
                last_heartbeat = now

            scan_once()

        except Exception as exc:
            error_event = base_event()
            error_event.update(
                {
                    "ts": utc_now(),
                    "event_type": "scan_error",
                    "severity": "medium",
                    "error": str(exc),
                }
            )
            emit_event(error_event)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()