"""Sandboxed command execution for assisted reproduction (Phase 4).

Deliberately **not** a container: true network/resource isolation requires one, and the
roadmap ships containers as the hard-isolation upgrade. This tool provides the practical
guardrails for the assisted-first workflow:

- **command vetting** — a blocklist rejects network tools, package installs, destructive
  filesystem and system commands;
- **timeout** — one command is capped (``RESEARCHOS_EXPERIMENT_TIMEOUT_S``);
- **directory isolation** — execution happens in the experiment's artifact directory;
- **secrets hygiene** — API keys/tokens are stripped from the child environment;
- **human approval gate** — nothing runs unless explicitly approved (CLI ``--yes`` or the
  ``experiment_allow_exec`` setting, which defaults to OFF).

Every run is recorded (exit code, output tail, duration) in the ``experiment`` table.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

from researchos.core.interfaces import ToolResult
from researchos.tools.base import BaseTool

# Substrings that signal network access, package installs, or destructive/system commands.
_BLOCKLIST = [
    "curl",
    "wget",
    "nc ",
    "ncat",
    "telnet",
    "ssh ",
    "scp ",
    "sftp",
    "pip install",
    "pip3 install",
    "npm install",
    "rm -rf",
    "rm -fr",
    "del /s",
    "rmdir /s",
    "format ",
    "diskpart",
    "shutdown",
    "taskkill",
    "reg add",
    "net user",
    "attrib",
    "certutil",
    "powershell",
    "pwsh",
    "cmd /c",
    "iwr",
    "irm",
    "invoke-webrequest",
    "invoke-expression",
    "start-process",
]

_SECRET_HINTS = ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")


def vet(command: str) -> str | None:
    """Return a reason string if the command violates the sandbox policy, else None."""
    lowered = command.lower().strip()
    if not lowered:
        return "empty command"
    for bad in _BLOCKLIST:
        if bad in lowered:
            return f"blocked pattern {bad!r}"
    if re.search(r"(?<![a-z0-9])(rm|mv|cp|mkfs|fdisk)\s+/(?![a-z0-9])", lowered):
        return "blocked root filesystem operation"
    return None


def _safe_env() -> dict[str, str]:
    """Child env without secrets — reproduction code must not see project keys."""
    return {
        k: v for k, v in os.environ.items() if not any(hint in k.upper() for hint in _SECRET_HINTS)
    }


class PythonExecTool(BaseTool):
    name = "python_exec"
    description = "Run a command in the experiment sandbox (requires human approval)."
    side_effects = True

    def __init__(
        self,
        artifacts_dir: Path,
        *,
        timeout_s: int = 60,
        allow_exec: bool = False,
    ) -> None:
        self._dir = artifacts_dir
        self._timeout = timeout_s
        self.allow_exec = allow_exec

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "approved": {"type": "boolean", "default": False},
            },
            "required": ["command"],
        }

    def invoke(self, **kwargs) -> ToolResult:
        command = str(kwargs.get("command", "")).strip()
        approved = bool(kwargs.get("approved", self.allow_exec))
        if not approved:
            return ToolResult(
                ok=False,
                error=(
                    "Execution not approved — the human-in-the-loop gate is closed. "
                    "Approve explicitly (CLI --yes / approved=True)."
                ),
            )
        violation = vet(command)
        if violation:
            return ToolResult(ok=False, error=f"Command blocked ({violation}): {command}")

        self._dir.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(self._dir),
                capture_output=True,
                text=True,
                timeout=self._timeout,
                env=_safe_env(),
            )
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, error=f"Command timed out after {self._timeout}s.")
        except OSError as exc:
            return ToolResult(ok=False, error=f"Failed to run command: {exc}")
        duration_ms = int((time.monotonic() - started) * 1000)

        output = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
        return ToolResult(
            ok=proc.returncode == 0,
            data={
                "exit_code": proc.returncode,
                "output": output[-8000:],
                "duration_ms": duration_ms,
            },
            error=None if proc.returncode == 0 else f"exit {proc.returncode}",
        )
