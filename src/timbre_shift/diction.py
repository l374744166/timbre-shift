"""Diction enhancement for converted vocals."""

from __future__ import annotations

import shutil
from pathlib import Path

from .commands import as_strs, run_command


DICTION_BLEND: dict[str, float] = {
    "off": 0.0,
    "light": 0.035,
    "medium": 0.060,
    "strong": 0.090,
}


def diction_blend(mode: str, consonant_blend: float | None = None) -> float:
    safe_mode = mode if mode in DICTION_BLEND else "light"
    if consonant_blend is not None:
        return max(0.0, min(float(consonant_blend), 0.12))
    return DICTION_BLEND[safe_mode]


def enhance_diction(
    converted_vocal: Path,
    source_vocal: Path,
    output: Path,
    mode: str = "light",
    consonant_blend: float | None = None,
) -> Path:
    safe_mode = mode if mode in DICTION_BLEND else "light"
    output.parent.mkdir(parents=True, exist_ok=True)
    if safe_mode == "off":
        if converted_vocal.resolve() != output.resolve():
            shutil.copy2(converted_vocal, output)
        return output

    blend = diction_blend(safe_mode, consonant_blend)
    presence_gain = {"light": 0.8, "medium": 1.2, "strong": 1.5}[safe_mode]
    air_gain = {"light": 0.4, "medium": 0.7, "strong": 1.0}[safe_mode]
    filter_complex = (
        "[1:a]highpass=f=3600,lowpass=f=9200,"
        "agate=threshold=0.018:ratio=1.8:attack=4:release=70,"
        f"volume={blend:.3f}[c];"
        "[0:a]highpass=f=70[base];"
        "[base][c]amix=inputs=2:duration=first:normalize=0,"
        f"equalizer=f=3500:t=q:w=1:g={presence_gain:.2f},"
        f"equalizer=f=6500:t=q:w=1.1:g={air_gain:.2f},"
        "deesser=i=0.25:m=0.45:f=0.45,"
        "alimiter=limit=0.95[out]"
    )
    run_command(
        as_strs(
            [
                "ffmpeg",
                "-y",
                "-i",
                converted_vocal,
                "-i",
                source_vocal,
                "-filter_complex",
                filter_complex,
                "-map",
                "[out]",
                "-ac",
                1,
                "-ar",
                44100,
                output,
            ]
        )
    )
    return output
