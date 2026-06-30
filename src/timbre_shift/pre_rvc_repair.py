"""Repair source vocals before RVC inference."""

from __future__ import annotations

import shutil
from pathlib import Path

from .commands import as_strs, run_command

VALID_REPAIR_MODES = {"off", "standard", "ai_generated", "deharsh_strong", "strong"}


def repair_source_vocal_before_rvc(
    source_vocal: Path,
    output: Path,
    mode: str = "off",
    problem_segments: list[dict] | None = None,
) -> Path:
    mode = mode if mode in VALID_REPAIR_MODES else "off"
    if mode == "strong":
        mode = "deharsh_strong"
    output.parent.mkdir(parents=True, exist_ok=True)
    if mode == "off":
        shutil.copy2(source_vocal, output)
        return output

    filters = _filters_for_mode(mode)
    run_command(
        as_strs(
            [
                "ffmpeg",
                "-y",
                "-i",
                source_vocal,
                "-af",
                ",".join(filters),
                "-ac",
                "1",
                "-ar",
                "44100",
                output,
            ]
        )
    )
    return output


def _filters_for_mode(mode: str) -> list[str]:
    if mode == "deharsh_strong":
        return [
            "highpass=f=80",
            "afftdn=nf=-31",
            "equalizer=f=3500:t=q:w=1.2:g=-2.2",
            "equalizer=f=6500:t=q:w=1.0:g=-2.4",
            "deesser=i=0.42:m=0.58:f=0.45",
            "lowpass=f=14000",
            "alimiter=limit=0.92",
            "loudnorm=I=-18:TP=-1.3:LRA=11",
        ]
    if mode == "ai_generated":
        return [
            "highpass=f=70",
            "afftdn=nf=-27",
            "equalizer=f=4200:t=q:w=1.0:g=-1.4",
            "equalizer=f=7600:t=q:w=1.0:g=-1.7",
            "deesser=i=0.34:m=0.52:f=0.45",
            "alimiter=limit=0.94",
            "loudnorm=I=-18:TP=-1.2:LRA=11",
        ]
    return [
        "highpass=f=70",
        "afftdn=nf=-24",
        "deesser=i=0.25:m=0.45:f=0.45",
        "alimiter=limit=0.95",
        "loudnorm=I=-18:TP=-1.2:LRA=11",
    ]
