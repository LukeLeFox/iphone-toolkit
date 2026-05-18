from __future__ import annotations

import shutil

from iphone_toolkit.core.command_runner import CommandResult, run_command


REQUIRED_COMMANDS = [
    "idevice_id",
    "ideviceinfo",
    "idevicediagnostics",
    "ideviceenterrecovery",
]

OPTIONAL_COMMANDS = [
    "irecovery",
]


def has_command(command: str) -> bool:
    return shutil.which(command) is not None


def check_dependencies() -> list[str]:
    return [cmd for cmd in REQUIRED_COMMANDS if shutil.which(cmd) is None]


def check_optional_dependencies() -> list[str]:
    return [cmd for cmd in OPTIONAL_COMMANDS if shutil.which(cmd) is None]


def list_devices() -> list[str]:
    result = run_command(["idevice_id", "-l"])

    if not result.ok or not result.stdout:
        return []

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def get_device_info(udid: str) -> CommandResult:
    return run_command(["ideviceinfo", "-u", udid], timeout=30)


def parse_device_info(raw_info: str) -> dict[str, str]:
    parsed: dict[str, str] = {}

    for line in raw_info.splitlines():
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        parsed[key.strip()] = value.strip()

    return parsed


def reboot_device() -> CommandResult:
    return run_command(["idevicediagnostics", "restart"], timeout=15)


def enter_recovery(udid: str) -> CommandResult:
    return run_command(["ideviceenterrecovery", udid], timeout=15)


def query_recovery_device() -> CommandResult:
    return run_command(["irecovery", "-q"], timeout=10)


def parse_recovery_mode(raw_info: str) -> str:
    for line in raw_info.splitlines():
        if line.upper().startswith("MODE:"):
            return line.split(":", 1)[1].strip()

    if raw_info.strip():
        return "Recovery/DFU"

    return "Unknown"


def get_connection_state() -> tuple[str, str]:
    """
    Returns:
      ("normal", udid)
      ("recovery", details)
      ("missing-irecovery", "")
      ("not-detected", "")
    """
    devices = list_devices()

    if devices:
        return "normal", devices[0]

    if not has_command("irecovery"):
        return "missing-irecovery", ""

    result = query_recovery_device()

    if result.ok and result.stdout:
        mode = parse_recovery_mode(result.stdout)
        return "recovery", mode

    return "not-detected", ""


def exit_recovery() -> CommandResult:
    return run_command(["irecovery", "-n"], timeout=15)
