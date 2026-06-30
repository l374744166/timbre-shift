"""RVC post-processing and comparison rendering helpers."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from .audio import export_mp3, mix_audio
from .deharsh import deharsh_converted_vocal
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
    deharsh_mode: str = "off",
) -> tuple[Path, dict[str, object]]:
    metrics: dict[str, object] = {
        "deharsh_mode": deharsh_mode,
        "deharsh_used": deharsh_mode != "off",
        "deharsh_seconds": 0.0,
        "diction_seconds": 0.0,
        "style_postprocess_seconds": 0.0,
        "consonant_blend": diction_blend(diction_mode, consonant_blend) if diction_mode != "off" else 0.0,
    }
    current = converted_vocal
    if deharsh_mode != "off":
        step_start = time.perf_counter()
        current = deharsh_converted_vocal(
            current,
            converted_dir / f"converted_deharsh_{deharsh_mode}.wav",
            mode=deharsh_mode,
        )
        metrics["deharsh_seconds"] = time.perf_counter() - step_start
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
            deharsh_mode="off",
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


def _render_ai_source_repair_variant(
    repaired_vocal: Path,
    source_vocal: Path,
    backing_track: Path | None,
    converted_dir: Path,
    output_dir: Path,
    mix_style_id: str = "natural",
) -> dict[str, object]:
    variants_dir = output_dir / "variants"
    variants_dir.mkdir(parents=True, exist_ok=True)
    mix_style = get_mix_style(mix_style_id)
    variant_id = "ai_source_repair"
    processed, post_metrics = _postprocess_rvc_vocal(
        converted_vocal=repaired_vocal,
        source_vocal=source_vocal,
        converted_dir=converted_dir / "variants" / variant_id,
        diction_mode="light",
        vocal_style="neutral",
        consonant_blend=None,
        deharsh_mode="medium",
    )
    wav_output = variants_dir / f"{variant_id}.wav"
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
    mp3_output = export_mp3(wav_output, variants_dir / f"{variant_id}.mp3")
    return {
        "id": variant_id,
        "name": "AI 源修复版",
        "description": "针对源人声高频沙哑、AI 毛刺和高潮段刺耳问题做了预清理和去刺处理。",
        "wav": str(wav_output),
        "mp3": str(mp3_output),
        "diction_mode": "light",
        "consonant_blend": post_metrics["consonant_blend"],
        "vocal_style": "neutral",
        "mix_style": mix_style.id,
        "pre_rvc_repair_mode": "ai_generated",
        "deharsh_mode": "medium",
    }
