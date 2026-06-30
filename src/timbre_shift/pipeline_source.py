"""Source vocal checks and pre-RVC repair preparation."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from .pipeline_config import PipelineOptions
from .pre_rvc_cleanup import preprocess_source_vocal_for_rvc
from .source_vocal_quality import analyze_source_vocal_quality

ProgressCallback = Callable[[str, int], None]


def prepare_conversion_source_vocal(
    *,
    options: PipelineOptions,
    engine_requires_training: bool,
    source_vocal: Path,
    converted_dir: Path,
    metrics: dict[str, object],
    update: ProgressCallback,
) -> Path:
    source_quality: dict[str, object] | None = None
    if options.source_vocal_quality_enabled and options.engine_id == "rvc_applio":
        update("检测源人声质量", 62)
        try:
            source_quality = analyze_source_vocal_quality(
                source_vocal,
                options.output_dir / "source_vocal_quality.json",
            )
            metrics["source_quality_metrics_path"] = str(options.output_dir / "source_vocal_quality.json")
            metrics["source_quality_score"] = source_quality.get("source_quality_score")
            metrics["source_quality_summary"] = source_quality.get("source_quality_summary")
            metrics["source_problem_segment_count"] = source_quality.get("source_problem_segment_count", 0)
            metrics["source_problem_segments"] = source_quality.get("problem_segments", [])
            metrics["source_has_clipping"] = bool(source_quality.get("source_has_clipping"))
            metrics["source_high_freq_risk"] = bool(source_quality.get("source_high_freq_risk"))
            metrics["source_harshness_risk"] = bool(source_quality.get("source_harshness_risk"))
        except Exception as exc:
            metrics["source_quality_error"] = str(exc)

    conversion_source_vocal = source_vocal
    if engine_requires_training:
        cleanup_mode = options.pre_rvc_cleanup_mode if options.pre_rvc_cleanup_mode in {"off", "standard", "strong", "ai_generated", "deharsh_strong", "noise_tolerant"} else "off"
        metrics["pre_rvc_cleanup_mode"] = cleanup_mode
        metrics["pre_rvc_repair_mode"] = cleanup_mode
        if cleanup_mode != "off":
            update("修复 RVC 输入人声", 66)
            step_start = time.perf_counter()
            conversion_source_vocal = preprocess_source_vocal_for_rvc(
                source_vocal,
                converted_dir / "pre_rvc_repair" / f"source_vocal_{cleanup_mode}.wav",
                mode=cleanup_mode,
            )
            repair_seconds = time.perf_counter() - step_start
            metrics["pre_rvc_cleanup_seconds"] = repair_seconds
            metrics["pre_rvc_cleanup_output"] = str(conversion_source_vocal)
            metrics["pre_rvc_repair_seconds"] = repair_seconds
            metrics["pre_rvc_repair_used"] = True
            metrics["pre_rvc_repair_output"] = str(conversion_source_vocal)
            metrics["problem_segments_repaired"] = metrics["source_problem_segment_count"]
    return conversion_source_vocal
