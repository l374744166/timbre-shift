"""Runtime helpers for invoking local Applio."""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


DEFAULT_APPLIO_DIR = Path("vendor/applio")


class ApplioCommandError(RuntimeError):
    def __init__(self, command: list[str], return_code: int, output_tail: list[str]) -> None:
        self.command = command
        self.return_code = return_code
        self.output_tail = output_tail
        super().__init__(f"Applio RVC 命令失败：{subprocess.CalledProcessError(return_code, command)}")


@dataclass(frozen=True)
class ApplioCheck:
    available: bool
    applio_dir: Path
    python: Path | None
    missing: list[str]


def resolve_applio_dir(applio_dir: Path | None = None) -> Path:
    return Path(os.environ.get("APPLIO_DIR") or applio_dir or DEFAULT_APPLIO_DIR).resolve()


def resolve_applio_python(applio_dir: Path) -> Path | None:
    env_python = os.environ.get("APPLIO_PYTHON")
    if env_python:
        return Path(env_python)
    candidates = [
        applio_dir / ".venv" / "bin" / "python",
        applio_dir / ".venv" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def check_applio(applio_dir: Path | None = None) -> ApplioCheck:
    root = resolve_applio_dir(applio_dir)
    missing: list[str] = []
    if not (root / "core.py").exists():
        missing.append(f"{root}/core.py")
    if not (root / "rvc" / "infer" / "infer.py").exists():
        missing.append(f"{root}/rvc/infer/infer.py")
    if not (root / "rvc" / "train" / "train.py").exists():
        missing.append(f"{root}/rvc/train/train.py")

    python = resolve_applio_python(root)
    if python is None or not python.exists():
        missing.append("APPLIO_PYTHON or vendor/applio/.venv/bin/python")

    return ApplioCheck(
        available=not missing,
        applio_dir=root,
        python=python if python and python.exists() else None,
        missing=missing,
    )


def _run_applio_python(
    applio_dir: Path,
    code: str,
    on_output: Callable[[str], None] | None = None,
) -> None:
    check = check_applio(applio_dir)
    if not check.python:
        raise RuntimeError("Applio Python 环境不存在，请先在 vendor/applio 运行 ./run-install.sh")
    env = os.environ.copy()
    env.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    env.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.0")
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    env.setdefault("NUMEXPR_NUM_THREADS", "1")
    env.setdefault("VECLIB_MAXIMUM_THREADS", "1")
    env.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    env.setdefault("KMP_INIT_AT_FORK", "FALSE")
    cache_dir = Path(
        os.environ.get("TIMBRE_SHIFT_APPLIO_CACHE_DIR")
        or Path(tempfile.gettempdir()) / "timbre-shift-applio-cache"
    )
    mpl_cache = cache_dir / "matplotlib"
    numba_cache = cache_dir / "numba"
    mpl_cache.mkdir(parents=True, exist_ok=True)
    numba_cache.mkdir(parents=True, exist_ok=True)
    env.setdefault("MPLCONFIGDIR", str(mpl_cache))
    env.setdefault("NUMBA_CACHE_DIR", str(numba_cache))
    command = [str(check.python), "-c", code]
    process = subprocess.Popen(
        command,
        cwd=applio_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    try:
        from .web_state import PROGRESS

        PROGRESS.register_process(process)
    except Exception:
        PROGRESS = None  # type: ignore[assignment]
    output_tail: list[str] = []
    try:
        if process.stdout:
            for line in process.stdout:
                print(line, end="")
                output_tail.append(line.rstrip())
                output_tail = output_tail[-40:]
                if on_output:
                    on_output(line.rstrip())
        return_code = process.wait()
    finally:
        try:
            if PROGRESS is not None:  # type: ignore[name-defined]
                PROGRESS.unregister_process(process)  # type: ignore[name-defined]
        except Exception:
            pass
    if return_code:
        raise ApplioCommandError(command, return_code, output_tail)
