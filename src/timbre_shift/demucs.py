"""Demucs vocal separation wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .commands import as_strs, run_command


@dataclass(frozen=True)
class SeparationResult:
    vocals: Path
    backing: Path


def separate_vocals(song: Path, output_dir: Path, model: str = "htdemucs_ft") -> SeparationResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_command(
        as_strs(
            [
                "demucs",
                "--two-stems=vocals",
                "-n",
                model,
                "-o",
                output_dir,
                song,
            ]
        )
    )
    stem_dir = output_dir / model / song.stem
    return SeparationResult(
        vocals=stem_dir / "vocals.wav",
        backing=stem_dir / "no_vocals.wav",
    )
