"""Seed-VC inference wrapper."""

from __future__ import annotations

import sys
from pathlib import Path

from .commands import as_strs, bool_arg, run_command


def convert_singing_voice(
    seed_vc_dir: Path,
    source_vocal: Path,
    target_voice: Path,
    output_dir: Path,
    diffusion_steps: int = 40,
    length_adjust: float = 1.0,
    inference_cfg_rate: float = 0.7,
    semi_tone_shift: int = 0,
    fp16: bool = True,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_command(
        as_strs(
            [
                sys.executable,
                "inference.py",
                "--source",
                source_vocal.resolve(),
                "--target",
                target_voice.resolve(),
                "--output",
                output_dir.resolve(),
                "--diffusion-steps",
                diffusion_steps,
                "--length-adjust",
                length_adjust,
                "--inference-cfg-rate",
                inference_cfg_rate,
                "--f0-condition",
                "True",
                "--auto-f0-adjust",
                "False",
                "--semi-tone-shift",
                semi_tone_shift,
                "--fp16",
                bool_arg(fp16),
            ]
        ),
        cwd=seed_vc_dir,
    )
    candidates = sorted(output_dir.glob("*.wav"), key=lambda path: path.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"Seed-VC did not write a wav file in {output_dir}")
    return candidates[-1]
