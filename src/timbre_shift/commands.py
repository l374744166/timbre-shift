"""Small subprocess helpers used by the local pipeline."""

from __future__ import annotations

import shutil
import subprocess
import os
from pathlib import Path
from typing import Iterable, List, Optional


def require_binary(name: str) -> Optional[str]:
    """Return a binary path when it exists on PATH."""
    return shutil.which(name)


def run_command(command: Iterable[str], cwd: Optional[Path] = None) -> None:
    printable = " ".join(str(part) for part in command)
    print("$", printable)
    env = os.environ.copy()
    try:
        import certifi

        env.setdefault("SSL_CERT_FILE", certifi.where())
        env.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    except Exception:
        pass
    subprocess.run(list(command), cwd=str(cwd) if cwd else None, env=env, check=True)


def bool_arg(value: bool) -> str:
    return "True" if value else "False"


def as_strs(parts: Iterable[object]) -> List[str]:
    return [str(part) for part in parts]
