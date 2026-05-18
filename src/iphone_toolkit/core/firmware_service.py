from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable


def get_log_dir() -> Path:
    log_dir = Path.home() / ".iphone-toolkit" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def create_restore_log_path(mode: str = "update") -> Path:
    safe_mode = "erase" if mode == "erase" else "update"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return get_log_dir() / f"{safe_mode}-restore-{timestamp}.log"


def validate_ipsw(path: str) -> tuple[bool, str]:
    if not path:
        return False, "Nessun file IPSW selezionato."

    ipsw = Path(path).expanduser()

    if not ipsw.exists():
        return False, f"File non trovato: {ipsw}"

    if not ipsw.is_file():
        return False, f"Il percorso non è un file: {ipsw}"

    if ipsw.suffix.lower() != ".ipsw":
        return False, "Il file selezionato non sembra un IPSW valido."

    return True, str(ipsw)


def build_update_command(ipsw_path: str) -> list[str]:
    """
    Dirty flash / update mode.

    No --erase flag is used here.
    The goal is to preserve user data.
    """
    return ["idevicerestore", ipsw_path]


def build_erase_command(ipsw_path: str) -> list[str]:
    """
    Full erase restore mode.

    WARNING: this wipes all user data.
    """
    return ["idevicerestore", "--erase", ipsw_path]


def run_restore_stream(
    ipsw_path: str,
    mode: str,
    on_line: Callable[[str], None],
    on_done: Callable[[int], None],
    log_path: Path | None = None,
) -> None:
    """
    Run idevicerestore and stream output line-by-line.

    mode:
      - update: preserve data, no --erase
      - erase: full restore, uses --erase
    """
    if mode == "erase":
        command = build_erase_command(ipsw_path)
        mode_label = "erase / factory restore"
        erase_flag = "enabled"
    else:
        command = build_update_command(ipsw_path)
        mode_label = "update / preserve data"
        erase_flag = "disabled"

    log_file = None

    try:
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = log_path.open("w", encoding="utf-8")

            def write_log(line: str) -> None:
                log_file.write(line + "\n")
                log_file.flush()
        else:
            def write_log(line: str) -> None:
                return None

        header_lines = [
            "=== iPhone Toolkit restore log ===",
            f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
            f"Mode: {mode_label}",
            f"Erase flag: {erase_flag}",
            "Command: " + " ".join(command),
            "",
        ]

        for line in header_lines:
            on_line(line)
            write_log(line)

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        assert process.stdout is not None

        for line in process.stdout:
            clean_line = line.rstrip()
            on_line(clean_line)
            write_log(clean_line)

        returncode = process.wait()

        footer = [
            "",
            f"[exit code] {returncode}",
            "=== end restore log ===",
        ]

        for line in footer:
            on_line(line)
            write_log(line)

        on_done(returncode)

    finally:
        if log_file is not None:
            log_file.close()


def run_update_restore_stream(
    ipsw_path: str,
    on_line: Callable[[str], None],
    on_done: Callable[[int], None],
    log_path: Path | None = None,
) -> None:
    run_restore_stream(
        ipsw_path=ipsw_path,
        mode="update",
        on_line=on_line,
        on_done=on_done,
        log_path=log_path,
    )


def run_erase_restore_stream(
    ipsw_path: str,
    on_line: Callable[[str], None],
    on_done: Callable[[int], None],
    log_path: Path | None = None,
) -> None:
    run_restore_stream(
        ipsw_path=ipsw_path,
        mode="erase",
        on_line=on_line,
        on_done=on_done,
        log_path=log_path,
    )
