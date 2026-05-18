from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run_command(command: list[str], timeout: int | None = 30) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        return CommandResult(
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
        )

    except FileNotFoundError as exc:
        return CommandResult(
            command=command,
            returncode=127,
            stdout="",
            stderr=f"Command not found: {exc.filename}",
        )

    except subprocess.TimeoutExpired:
        return CommandResult(
            command=command,
            returncode=124,
            stdout="",
            stderr=f"Command timed out after {timeout} seconds",
        )

    except Exception as exc:
        return CommandResult(
            command=command,
            returncode=1,
            stdout="",
            stderr=f"Unexpected error: {exc}",
        )
