"""Small subprocess helpers used by the local pipeline."""

from __future__ import annotations

import shutil
import subprocess
import os
from pathlib import Path
from typing import Iterable, List, Mapping, Optional


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
    env.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
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
    subprocess.run(command_list, cwd=str(cwd) if cwd else None, env=build_env(extra_env), check=True)


def bool_arg(value: bool) -> str:
    return "True" if value else "False"


def as_strs(parts: Iterable[object]) -> List[str]:
    return [str(part) for part in parts]
