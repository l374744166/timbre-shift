"""Pipeline configuration and render presets."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .library import DEFAULT_DB_PATH, DEFAULT_LIBRARY_DIR


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
class RenderPreset:
    name: str
    clip_seconds: Optional[int]
    demucs_model: str
    demucs_overlap: float
    diffusion_steps: int
    inference_cfg_rate: float
    reference_seconds: int = 60
    compact_vocals: bool = False
    demucs_shifts: int = 0
    device: str = "mps"
    output_mp3: bool = True


PRESETS: dict[str, RenderPreset] = {
    "preview_auto_15_m2max": RenderPreset("15秒自动试听", 15, "htdemucs", 0.10, 4, 0.0, 8, False),
    "m2max_hq_30": RenderPreset("M2 Max默认整首", None, "htdemucs", 0.10, 16, 0.0, 16, True),
    "m2max_hq_plus": RenderPreset("M2 Max高质量Plus", None, "htdemucs", 0.10, 20, 0.2, 20, True),
    "m2max_offline_max": RenderPreset("离线最高质量", None, "htdemucs_ft", 0.25, 25, 0.7, 25, True),
    "preview_fast": RenderPreset("极速试听", 30, "htdemucs", 0.10, 4, 0.0, 20),
    "preview_balanced": RenderPreset("普通试听", 30, "htdemucs", 0.10, 10, 0.0, 30),
    "m2_full_fast": RenderPreset("M2整首快速", None, "htdemucs", 0.10, 12, 0.0, 15, True),
    "m2_full_safe": RenderPreset("M2整首稳妥", None, "htdemucs", 0.12, 16, 0.0, 18, True),
    "full_fast": RenderPreset("整首快速", None, "htdemucs", 0.10, 10, 0.0, 30),
    "full_quality": RenderPreset("整首高质量", None, "htdemucs_ft", 0.25, 25, 0.7, 60),
}


@dataclass(frozen=True)
class PipelineOptions:
    voice: Optional[Path] = None
    song: Optional[Path] = None
    seed_vc_dir: Path = Path("vendor/seed-vc")
    work_dir: Path = Path("data/processed/demo")
    output_dir: Path = Path("outputs")
    cache_dir: Path = Path("data/cache")
    library_dir: Path = DEFAULT_LIBRARY_DIR
    library_db_path: Path = DEFAULT_DB_PATH
    render_mode: str = "m2max_hq_30"
    demucs_model: Optional[str] = None
    demucs_overlap: Optional[float] = None
    diffusion_steps: Optional[int] = None
    length_adjust: float = 1.0
    inference_cfg_rate: Optional[float] = None
    semi_tone_shift: int = 0
    fp16: Optional[bool] = None
    clip_seconds: Optional[int] = None
    reference_seconds: Optional[int] = None
    device: str = "mps"
    skip_separation: bool = False
    compact_vocals: Optional[bool] = None
    voice_profile_id: Optional[str] = None
    song_id: Optional[str] = None
    save_voice_to_library: bool = False
    save_song_to_library: bool = False
    voice_name: Optional[str] = None
    voice_description: Optional[str] = None
    song_title: Optional[str] = None
    song_artist: Optional[str] = None
    rights_confirmed: bool = False
    source_mode: str = "full_song"
    polish_converted_vocal: bool = True
    seedvc_chunk_seconds: int = 0
    seedvc_chunk_workers: int = 0
    engine_id: str = "seedvc"


def resolve_preset(options: PipelineOptions) -> RenderPreset:
    if options.render_mode not in PRESETS:
        available = ", ".join(sorted(PRESETS))
        raise ValueError(f"Unknown render_mode={options.render_mode}. Available: {available}")
    base = PRESETS[options.render_mode]
    return RenderPreset(
        name=base.name,
        clip_seconds=options.clip_seconds if options.clip_seconds is not None else base.clip_seconds,
        demucs_model=options.demucs_model or base.demucs_model,
        demucs_overlap=options.demucs_overlap if options.demucs_overlap is not None else base.demucs_overlap,
        diffusion_steps=options.diffusion_steps if options.diffusion_steps is not None else base.diffusion_steps,
        inference_cfg_rate=(
            options.inference_cfg_rate if options.inference_cfg_rate is not None else base.inference_cfg_rate
        ),
        reference_seconds=options.reference_seconds if options.reference_seconds is not None else base.reference_seconds,
        compact_vocals=options.compact_vocals if options.compact_vocals is not None else base.compact_vocals,
        demucs_shifts=base.demucs_shifts,
        device=options.device or base.device,
        output_mp3=base.output_mp3,
    )


def seedvc_chunk_settings(options: PipelineOptions, preset: RenderPreset) -> tuple[int, int]:
    if preset.clip_seconds:
        return 0, 1
    chunk_seconds = options.seedvc_chunk_seconds
    workers = options.seedvc_chunk_workers
    if not chunk_seconds:
        chunk_seconds = int(os.environ.get("TIMBRE_SHIFT_SEEDVC_CHUNK_SECONDS", "0") or "0")
    if chunk_seconds <= 0:
        return 0, 1
    if not workers:
        workers = int(os.environ.get("TIMBRE_SHIFT_SEEDVC_CHUNK_WORKERS", "2") or "1")
    return max(0, chunk_seconds), max(1, workers)
