"""Small subprocess helpers used by the local pipeline."""

from __future__ import annotations

import shutil
import subprocess
import os
import time
from pathlib import Path
from typing import Iterable, List, Mapping, Optional


class CommandExecutionError(subprocess.CalledProcessError):
    """CalledProcessError with a concise stderr tail for web-facing failures."""

    def __str__(self) -> str:
        base = super().__str__()
        detail = _tail_text(self.stderr or self.output)
        return f"{base}\n{detail}" if detail else base


def require_binary(name: str) -> Optional[str]:
    """Return a binary path when it exists on PATH."""
    return shutil.which(name)


def build_env(extra_env: Mapping[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    try:
        import certifi

        env.setdefault("SSL_CERT_FILE", certifi.where())
        env.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    except Exception:
        pass
    if extra_env:
        for key, value in extra_env.items():
            if value is not None:
                env[key] = str(value)
    return env


def run_command(
    command: Iterable[str],
    cwd: Optional[Path] = None,
    extra_env: Mapping[str, str] | None = None,
) -> None:
    command_list = list(command)
    printable = " ".join(str(part) for part in command_list)
    print("$", printable)
    process = subprocess.Popen(
        command_list,
        cwd=str(cwd) if cwd else None,
        env=build_env(extra_env),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        from .web_state import PROGRESS

        PROGRESS.register_process(process)
    except Exception:
        PROGRESS = None  # type: ignore[assignment]
    stdout = ""
    stderr = ""
    try:
        while True:
            try:
                out, err = process.communicate(timeout=0.25)
                stdout += out or ""
                stderr += err or ""
                break
            except subprocess.TimeoutExpired:
                continue
    finally:
        try:
            if PROGRESS is not None:  # type: ignore[name-defined]
                PROGRESS.unregister_process(process)  # type: ignore[name-defined]
        except Exception:
            pass
    if process.returncode != 0:
        raise CommandExecutionError(
            process.returncode or 1,
            command_list,
            output=stdout,
            stderr=stderr,
        )


def bool_arg(value: bool) -> str:
    return "True" if value else "False"


def as_strs(parts: Iterable[object]) -> List[str]:
    return [str(part) for part in parts]


def _tail_text(value: str | None, max_lines: int = 8) -> str:
    if not value:
        return ""
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    return "\n".join(lines[-max_lines:])
