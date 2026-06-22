"""Conservative vocal style post-processing."""

from __future__ import annotations

import shutil
from pathlib import Path

from .commands import as_strs, run_command


STYLE_FILTERS: dict[str, list[str]] = {
    "neutral": [
        "highpass=f=70",
        "acompressor=threshold=-20dB:ratio=1.8:attack=10:release=90:makeup=1.2",
        "alimiter=limit=0.94",
    ],
    "close_intimate": [
        "highpass=f=75",
        "equalizer=f=3000:t=q:w=1:g=1.2",
        "equalizer=f=4500:t=q:w=1.2:g=0.8",
        "deesser=i=0.30:m=0.50:f=0.45",
        "acompressor=threshold=-20dB:ratio=2.4:attack=6:release=70:makeup=1.6",
        "alimiter=limit=0.94",
    ],
    "soft": [
        "highpass=f=65",
        "equalizer=f=240:t=q:w=1.0:g=1.0",
        "equalizer=f=8500:t=q:w=1.0:g=-0.8",
        "acompressor=threshold=-22dB:ratio=1.7:attack=18:release=140:makeup=1.4",
        "aecho=0.12:0.18:38:0.08",
        "alimiter=limit=0.94",
    ],
    "warm": [
        "highpass=f=55",
        "equalizer=f=180:t=q:w=1.0:g=1.3",
        "equalizer=f=3200:t=q:w=1.1:g=-0.4",
        "equalizer=f=9000:t=q:w=1.0:g=-1.0",
        "acompressor=threshold=-21dB:ratio=1.9:attack=12:release=120:makeup=1.4",
        "alimiter=limit=0.94",
    ],
    "narrative_soft": [
        "highpass=f=58",
        "equalizer=f=220:t=q:w=1.0:g=0.9",
        "equalizer=f=2800:t=q:w=1.1:g=-0.6",
        "equalizer=f=7600:t=q:w=1.0:g=-1.2",
        "deesser=i=0.22:m=0.42:f=0.45",
        "acompressor=threshold=-23dB:ratio=1.55:attack=20:release=150:makeup=1.25",
        "alimiter=limit=0.94",
    ],
    "low_thick": [
        "highpass=f=48",
        "equalizer=f=160:t=q:w=1.0:g=1.8",
        "equalizer=f=420:t=q:w=1.1:g=0.7",
        "equalizer=f=3600:t=q:w=1.2:g=-0.8",
        "equalizer=f=8500:t=q:w=1.0:g=-1.4",
        "acompressor=threshold=-22dB:ratio=2.0:attack=14:release=130:makeup=1.35",
        "alimiter=limit=0.94",
    ],
    "bright_pop": [
        "highpass=f=75",
        "equalizer=f=3800:t=q:w=1.0:g=1.2",
        "equalizer=f=8000:t=q:w=1.1:g=0.8",
        "deesser=i=0.35:m=0.55:f=0.45",
        "acompressor=threshold=-19dB:ratio=2.5:attack=5:release=65:makeup=1.5",
        "alimiter=limit=0.94",
    ],
}


def supported_styles() -> set[str]:
    return set(STYLE_FILTERS)


def apply_vocal_style(vocal: Path, output: Path, style: str = "neutral") -> Path:
    aliases = {
        "soft_ballad": "soft",
        "warm_low_male": "warm",
        "target_narrative": "narrative_soft",
        "target_low_thick": "low_thick",
    }
    safe_style = aliases.get(style, style)
    safe_style = safe_style if safe_style in STYLE_FILTERS else "neutral"
    output.parent.mkdir(parents=True, exist_ok=True)
    filters = ",".join(STYLE_FILTERS[safe_style])
    if safe_style == "neutral" and vocal.resolve() == output.resolve():
        return output
    run_command(
        as_strs(
            [
                "ffmpeg",
                "-y",
                "-i",
                vocal,
                "-af",
                filters,
                "-ac",
                1,
                "-ar",
                44100,
                output,
            ]
        )
    )
    if not output.exists() and vocal.exists():
        shutil.copy2(vocal, output)
    return output
