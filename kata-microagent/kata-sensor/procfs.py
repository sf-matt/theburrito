import os


def read_text(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return None


def read_bytes(path: str) -> bytes | None:
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception:
        return None


def list_pids():
    for entry in os.listdir("/proc"):
        if entry.isdigit():
            yield entry


def get_process_name(pid: str) -> str | None:
    data = read_text(f"/proc/{pid}/comm")
    return data.strip() if data else None


def get_cmdline(pid: str) -> str:
    data = read_bytes(f"/proc/{pid}/cmdline")
    if not data:
        return ""
    return data.replace(b"\x00", b" ").decode(errors="ignore").strip()


def get_ppid(pid: str) -> int | None:
    status = read_text(f"/proc/{pid}/status")
    if not status:
        return None
    for line in status.splitlines():
        if line.startswith("PPid:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def get_uid(pid: str) -> int | None:
    status = read_text(f"/proc/{pid}/status")
    if not status:
        return None
    for line in status.splitlines():
        if line.startswith("Uid:"):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    return int(parts[1])
                except ValueError:
                    return None
    return None


def get_exe_path(pid: str) -> str:
    try:
        return os.path.realpath(f"/proc/{pid}/exe")
    except Exception:
        return ""