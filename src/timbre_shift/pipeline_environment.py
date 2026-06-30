"""Pipeline environment and input validation helpers."""

from __future__ import annotations

import sys
from pathlib import Path

from .commands import require_binary
from .pipeline_config import EnvironmentReport, PipelineOptions


def check_pipeline_environment(seed_vc_dir: Path) -> EnvironmentReport:
    checks: list[str] = []
    missing: list[str] = []

    if Path(sys.executable).exists():
        checks.append(f"python: {sys.executable}")
    else:
        missing.append("python")

    for binary in ["ffmpeg", "demucs"]:
        if require_binary(binary):
            checks.append(binary)
        else:
            missing.append(binary)

    inference = seed_vc_dir / "inference.py"
    if inference.exists():
        checks.append(str(inference))
    else:
        missing.append(f"{inference} (clone Seed-VC here or pass --seed-vc-dir)")

    return EnvironmentReport(checks=checks, missing=missing)


def validate_pipeline_inputs(options: PipelineOptions) -> None:
    if not options.voice_profile_id and (not options.voice or not options.voice.exists()):
        raise FileNotFoundError(f"Voice reference not found: {options.voice}")
    if not options.song_id and (not options.song or not options.song.exists()):
        raise FileNotFoundError(f"Song not found: {options.song}")
    if not (options.seed_vc_dir / "inference.py").exists():
        raise FileNotFoundError(f"Seed-VC inference.py not found in: {options.seed_vc_dir}")
