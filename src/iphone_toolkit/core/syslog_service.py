from __future__ import annotations

from datetime import datetime
from pathlib import Path


def get_log_dir() -> Path:
    log_dir = Path.home() / ".iphone-toolkit" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def create_syslog_log_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return get_log_dir() / f"syslog-{timestamp}.log"


def build_syslog_command(udid: str | None = None) -> list[str]:
    if udid:
        return ["idevicesyslog", "-u", udid]

    return ["idevicesyslog"]
