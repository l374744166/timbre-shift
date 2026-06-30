"""Post-RVC de-harshing filters."""

from __future__ import annotations

import shutil
from pathlib import Path

from .commands import as_strs, run_command

VALID_DEHARSH_MODES = {"off", "light", "medium", "strong"}


def deharsh_converted_vocal(converted_vocal: Path, output: Path, mode: str = "off") -> Path:
    mode = mode if mode in VALID_DEHARSH_MODES else "off"
    output.parent.mkdir(parents=True, exist_ok=True)
    if mode == "off":
        shutil.copy2(converted_vocal, output)
        return output
    run_command(
        as_strs(
            [
                "ffmpeg",
                "-y",
                "-i",
                converted_vocal,
                "-af",
                ",".join(_filters_for_mode(mode)),
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
    if mode == "strong":
        return [
            "equalizer=f=3500:t=q:w=1.0:g=-2.0",
            "equalizer=f=6800:t=q:w=1.0:g=-2.4",
            "deesser=i=0.45:m=0.6:f=0.45",
            "lowpass=f=13000",
            "alimiter=limit=0.92",
        ]
    if mode == "medium":
        return [
            "equalizer=f=3500:t=q:w=1.1:g=-1.3",
            "equalizer=f=6500:t=q:w=1.0:g=-1.8",
            "deesser=i=0.35:m=0.55:f=0.45",
            "alimiter=limit=0.93",
        ]
    return [
        "equalizer=f=7200:t=q:w=1.0:g=-1.0",
        "deesser=i=0.25:m=0.48:f=0.45",
        "alimiter=limit=0.94",
    ]
