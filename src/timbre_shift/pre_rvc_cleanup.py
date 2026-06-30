"""Pre-clean source vocals before RVC inference."""

from __future__ import annotations

import shutil
from pathlib import Path

from .commands import as_strs, run_command
from .pre_rvc_repair import repair_source_vocal_before_rvc


def preprocess_source_vocal_for_rvc(source_vocal: Path, output: Path, mode: str = "standard") -> Path:
    if mode in {"ai_generated", "deharsh_strong"}:
        return repair_source_vocal_before_rvc(source_vocal, output, mode=mode)
    mode = mode if mode in {"off", "standard", "strong"} else "standard"
    output.parent.mkdir(parents=True, exist_ok=True)
    if mode == "off":
        shutil.copy2(source_vocal, output)
        return output

    if mode == "strong":
        filters = [
            "highpass=f=90",
            "lowpass=f=15500",
            "afftdn=nf=-30",
            "deesser=i=0.38:m=0.55:f=0.45",
            "acompressor=threshold=-22dB:ratio=2.0:attack=8:release=80:makeup=1.4",
            "alimiter=limit=0.95",
            "loudnorm=I=-18:TP=-1.2:LRA=11",
        ]
    else:
        filters = [
            "highpass=f=70",
            "lowpass=f=16000",
            "afftdn=nf=-25",
            "deesser=i=0.25:m=0.45:f=0.45",
            "alimiter=limit=0.95",
            "loudnorm=I=-18:TP=-1.2:LRA=11",
        ]

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
