"""RVC post-processing and automatic comparison variant orchestration."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from .pipeline_config import PipelineOptions
from .pre_rvc_repair import repair_source_vocal_before_rvc
from .source_vocal_quality import analyze_source_vocal_quality
from .vocal_segments import map_compact_problem_segments, restore_compact_vocals
from .pipeline_rvc import (
    _postprocess_rvc_vocal,
    _render_ai_source_repair_variant,
    _render_localized_repair_variant,
    _render_rvc_variants,
)

ProgressCallback = Callable[[str, int], None]


def _restore_variant_vocal_if_needed(
    converted_variant: Path,
    output: Path,
    compact_result,
) -> Path:
    if compact_result is None:
        return converted_variant
    return restore_compact_vocals(
        converted_compact=converted_variant,
        output=output,
        segments=compact_result.segments,
        total_duration=compact_result.total_duration,
    )


def _timeline_problem_segments(problem_segments: list[dict], compact_result) -> list[dict]:
    if compact_result is None:
        return problem_segments
    return map_compact_problem_segments(problem_segments, compact_result.segments)


def postprocess_rvc_output(
    *,
    options: PipelineOptions,
    converted_vocal: Path,
    source_vocal: Path,
    diagnostic_source_vocal: Path,
    converted_dir: Path,
    metrics: dict[str, object],
    requested_diction_mode: str,
    requested_vocal_style: str,
    rvc_preset,
    backing_track: Path | None,
    mix_style,
    compact_result,
    engine,
    voice_model,
    rvc_convert_options: dict[str, object] | None,
    update: ProgressCallback,
) -> tuple[Path, Path]:
    raw_converted_vocal = converted_vocal
    update("增强咬字和人声修饰", 90)
    converted_vocal, rvc_post_metrics = _postprocess_rvc_vocal(
        converted_vocal=converted_vocal,
        source_vocal=diagnostic_source_vocal,
        converted_dir=converted_dir,
        diction_mode=requested_diction_mode,
        vocal_style=requested_vocal_style,
        consonant_blend=rvc_preset.consonant_blend,
        deharsh_mode=options.deharsh_mode if options.deharsh_mode in {"off", "light", "medium", "strong", "rescue"} else "off",
    )
    metrics.update(rvc_post_metrics)
    metrics["polished_vocal_wav"] = str(converted_vocal)
    try:
        converted_quality = analyze_source_vocal_quality(raw_converted_vocal, segment_seconds=5.0)
        metrics["converted_harshness_score"] = converted_quality.get("harshness_score")
    except Exception:
        pass
    if options.generate_variants:
        update("生成 A/B 对比版本", 91)
        variants = _render_rvc_variants(
            base_vocal=raw_converted_vocal,
            source_vocal=diagnostic_source_vocal,
            backing_track=backing_track,
            converted_dir=converted_dir,
            output_dir=options.output_dir,
            mix_style_id=mix_style.id,
            exclude_preset_id=rvc_preset.id,
        )
        source_risky = bool(
            metrics["source_problem_segment_count"]
            or metrics["source_high_freq_risk"]
            or metrics["source_harshness_risk"]
            or metrics["source_has_clipping"]
            or (isinstance(metrics.get("converted_harshness_score"), (int, float)) and float(metrics["converted_harshness_score"]) >= 0.72)
        )
        if source_risky and engine is not None and voice_model is not None and rvc_convert_options is not None:
            try:
                update("生成 AI 源修复对比版", 91)
                step_start = time.perf_counter()
                repaired_source = repair_source_vocal_before_rvc(
                    source_vocal,
                    converted_dir / "pre_rvc_repair" / "source_vocal_ai_variant.wav",
                    mode="ai_generated",
                    problem_segments=metrics["source_problem_segments"] if isinstance(metrics["source_problem_segments"], list) else None,
                )
                repair_variant_result = engine.convert(
                    source_vocal=repaired_source,
                    target_voice_or_model=Path(voice_model.model_path),
                    output_dir=converted_dir / options.engine_id / "ai_source_repair",
                    options=rvc_convert_options,
                )
                repair_variant_vocal = _restore_variant_vocal_if_needed(
                    repair_variant_result.converted_vocal_path,
                    converted_dir / options.engine_id / "ai_source_repair" / "converted_full_timeline.wav",
                    compact_result,
                )
                variants.append(
                    _render_ai_source_repair_variant(
                        repaired_vocal=repair_variant_vocal,
                        source_vocal=diagnostic_source_vocal,
                        backing_track=backing_track,
                        converted_dir=converted_dir,
                        output_dir=options.output_dir,
                        mix_style_id=mix_style.id,
                    )
                )
                repaired_source_rescue = repair_source_vocal_before_rvc(
                    source_vocal,
                    converted_dir / "pre_rvc_repair" / "source_vocal_noise_tolerant_variant.wav",
                    mode="noise_tolerant",
                    problem_segments=metrics["source_problem_segments"] if isinstance(metrics["source_problem_segments"], list) else None,
                )
                rescue_result = engine.convert(
                    source_vocal=repaired_source_rescue,
                    target_voice_or_model=Path(voice_model.model_path),
                    output_dir=converted_dir / options.engine_id / "noise_tolerant",
                    options=rvc_convert_options,
                )
                rescue_vocal = _restore_variant_vocal_if_needed(
                    rescue_result.converted_vocal_path,
                    converted_dir / options.engine_id / "noise_tolerant" / "converted_full_timeline.wav",
                    compact_result,
                )
                variants.append(
                    _render_ai_source_repair_variant(
                        repaired_vocal=rescue_vocal,
                        source_vocal=diagnostic_source_vocal,
                        backing_track=backing_track,
                        converted_dir=converted_dir,
                        output_dir=options.output_dir,
                        mix_style_id=mix_style.id,
                        variant_id="noise_tolerant_rescue",
                        name="噪音歌保底版",
                        description="更强压制沙哑、毛刺和刺耳高频；可能更暗，但优先保证不炸不刺。",
                        deharsh_mode="rescue",
                        repair_mode="noise_tolerant",
                    )
                )
                localized_segments = _timeline_problem_segments(
                    metrics["source_problem_segments"] if isinstance(metrics["source_problem_segments"], list) else [],
                    compact_result,
                )
                if localized_segments:
                    variants.append(
                        _render_localized_repair_variant(
                            base_vocal=raw_converted_vocal,
                            rescue_vocal=rescue_vocal,
                            source_vocal=diagnostic_source_vocal,
                            backing_track=backing_track,
                            problem_segments=localized_segments,
                            converted_dir=converted_dir,
                            output_dir=options.output_dir,
                            mix_style_id=mix_style.id,
                        )
                    )
                metrics["auto_repair_variant_generated"] = True
                metrics["auto_repair_reason"] = "检测到源人声高潮段可能有沙哑、毛刺或刺耳高频"
                metrics["auto_repair_variant_seconds"] = time.perf_counter() - step_start
            except Exception as exc:
                metrics["auto_repair_variant_error"] = str(exc)
        metrics["variants"] = variants
    return converted_vocal, raw_converted_vocal
