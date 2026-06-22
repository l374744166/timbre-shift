"""RVC post-processing and comparison rendering helpers."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from .audio import export_mp3, mix_audio
from .diction import diction_blend, enhance_diction
from .mix_styles import get_mix_style
from .rvc_presets import get_rvc_preset, variant_preset_ids
from .style_postprocess import apply_vocal_style


def _postprocess_rvc_vocal(
    converted_vocal: Path,
    source_vocal: Path,
    converted_dir: Path,
    diction_mode: str,
    vocal_style: str,
    consonant_blend: float | None,
) -> tuple[Path, dict[str, object]]:
    metrics: dict[str, object] = {
        "diction_seconds": 0.0,
        "style_postprocess_seconds": 0.0,
        "consonant_blend": diction_blend(diction_mode, consonant_blend) if diction_mode != "off" else 0.0,
    }
    current = converted_vocal
    if diction_mode != "off":
        step_start = time.perf_counter()
        current = enhance_diction(
            converted_vocal=current,
            source_vocal=source_vocal,
            output=converted_dir / f"converted_diction_{diction_mode}.wav",
            mode=diction_mode,
            consonant_blend=consonant_blend,
        )
        metrics["diction_seconds"] = time.perf_counter() - step_start
    step_start = time.perf_counter()
    current = apply_vocal_style(
        current,
        converted_dir / f"converted_style_{vocal_style}.wav",
        style=vocal_style,
    )
    metrics["style_postprocess_seconds"] = time.perf_counter() - step_start
    return current, metrics


def _render_rvc_variants(
    base_vocal: Path,
    source_vocal: Path,
    backing_track: Path | None,
    converted_dir: Path,
    output_dir: Path,
    mix_style_id: str = "natural",
) -> list[dict[str, object]]:
    variants_dir = output_dir / "variants"
    variants_dir.mkdir(parents=True, exist_ok=True)
    mix_style = get_mix_style(mix_style_id)
    rendered: list[dict[str, object]] = []
    for preset_id in variant_preset_ids():
        preset = get_rvc_preset(preset_id)
        variant_dir = converted_dir / "variants" / preset_id
        processed, post_metrics = _postprocess_rvc_vocal(
            converted_vocal=base_vocal,
            source_vocal=source_vocal,
            converted_dir=variant_dir,
            diction_mode=preset.diction_mode,
            vocal_style=preset.vocal_style,
            consonant_blend=preset.consonant_blend,
        )
        wav_output = variants_dir / f"{preset_id}.wav"
        if backing_track is None:
            shutil.copy2(processed, wav_output)
        else:
            mix_audio(
                processed,
                backing_track,
                wav_output,
                vocal_volume=mix_style.vocal_gain,
                backing_volume=mix_style.backing_gain,
                limiter=0.92,
            )
        mp3_output = export_mp3(wav_output, variants_dir / f"{preset_id}.mp3")
        rendered.append(
            {
                "id": preset_id,
                "name": preset.name,
                "wav": str(wav_output),
                "mp3": str(mp3_output),
                "diction_mode": preset.diction_mode,
                "consonant_blend": post_metrics["consonant_blend"],
                "vocal_style": preset.vocal_style,
                "mix_style": mix_style.id,
            }
        )
    return rendered
