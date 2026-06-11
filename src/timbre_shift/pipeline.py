"""Local demo orchestration for Timbre Shift."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

from .audio import mix_audio, normalize_audio
from .commands import require_binary
from .demucs import separate_vocals
from .seed_vc import convert_singing_voice


@dataclass(frozen=True)
class EnvironmentReport:
    checks: List[str]
    missing: List[str]

    @property
    def ready(self) -> bool:
        return not self.missing

    def to_text(self) -> str:
        lines = ["Timbre Shift environment check"]
        lines.extend(f"OK: {item}" for item in self.checks)
        lines.extend(f"Missing: {item}" for item in self.missing)
        return "\n".join(lines)


@dataclass(frozen=True)
class PipelineOptions:
    voice: Path
    song: Path
    seed_vc_dir: Path
    work_dir: Path = Path("data/processed/demo")
    output_dir: Path = Path("outputs")
    demucs_model: str = "htdemucs_ft"
    diffusion_steps: int = 40
    length_adjust: float = 1.0
    inference_cfg_rate: float = 0.7
    semi_tone_shift: int = 0
    fp16: bool = True


def check_environment(seed_vc_dir: Path) -> EnvironmentReport:
    checks: List[str] = []
    missing: List[str] = []

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


def validate_inputs(options: PipelineOptions) -> None:
    if not options.voice.exists():
        raise FileNotFoundError(f"Voice reference not found: {options.voice}")
    if not options.song.exists():
        raise FileNotFoundError(f"Song not found: {options.song}")
    if not (options.seed_vc_dir / "inference.py").exists():
        raise FileNotFoundError(f"Seed-VC inference.py not found in: {options.seed_vc_dir}")


def run_demo(options: PipelineOptions) -> Path:
    validate_inputs(options)

    prepared_dir = options.work_dir / "prepared"
    separated_dir = options.work_dir / "separated"
    converted_dir = options.work_dir / "converted"

    prepared_voice = normalize_audio(options.voice, prepared_dir / "target_voice.wav")
    prepared_song = normalize_audio(options.song, prepared_dir / "song.wav")

    separation = separate_vocals(
        prepared_song,
        output_dir=separated_dir,
        model=options.demucs_model,
    )
    if not separation.vocals.exists() or not separation.backing.exists():
        raise FileNotFoundError(f"Demucs output not found under {separated_dir}")

    converted_vocal = convert_singing_voice(
        seed_vc_dir=options.seed_vc_dir,
        source_vocal=separation.vocals,
        target_voice=prepared_voice,
        output_dir=converted_dir,
        diffusion_steps=options.diffusion_steps,
        length_adjust=options.length_adjust,
        inference_cfg_rate=options.inference_cfg_rate,
        semi_tone_shift=options.semi_tone_shift,
        fp16=options.fp16,
    )

    return mix_audio(
        converted_vocal=converted_vocal,
        backing_track=separation.backing,
        output=options.output_dir / "final.wav",
    )
