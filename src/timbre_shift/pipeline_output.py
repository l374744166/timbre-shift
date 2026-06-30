"""Final output rendering, diagnostics, and history archiving."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Callable

from .audio import export_mp3, limit_audio_peak, mix_audio
from .diagnostics import AnalyzerContext, analyze_generation
from .generation_history import archive_generation_history
from .pipeline_config import PipelineOptions, RenderPreset

ProgressCallback = Callable[[str, int], None]


def finalize_generation_outputs(
    *,
    options: PipelineOptions,
    preset: RenderPreset,
    metrics: dict[str, object],
    converted_vocal: Path,
    raw_converted_vocal: Path,
    diagnostic_source_vocal: Path,
    backing_track: Path | None,
    mix_style,
    voice_profile,
    song_record,
    total_start: float,
    update: ProgressCallback,
) -> Path:
    dry_vocal_output = options.output_dir / "dry_vocal.wav"
    dry_vocal_output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(converted_vocal, dry_vocal_output)
    metrics["output_dry_vocal_wav"] = str(dry_vocal_output)

    if backing_track is None:
        update("导出已换声人声", 92)
        final_output = options.output_dir / "final.wav"
        final_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(converted_vocal, final_output)
    else:
        update("混音导出", 92)
        step_start = time.perf_counter()
        final_output = mix_audio(
            converted_vocal=converted_vocal,
            backing_track=backing_track,
            output=options.output_dir / "final.wav",
            vocal_volume=mix_style.vocal_gain,
            backing_volume=mix_style.backing_gain,
            limiter=0.92 if options.enable_safe_limiter else 0.95,
        )
        metrics["mix_seconds"] = time.perf_counter() - step_start

    if options.enable_safe_limiter:
        update("最终防爆音处理", 94)
        step_start = time.perf_counter()
        limited_output = options.output_dir / "final_limited.wav"
        unlimited_output = options.output_dir / "final_unlimited.wav"
        unlimited_output.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(final_output, unlimited_output)
            metrics["final_unlimited_wav"] = str(unlimited_output)
            final_output = limit_audio_peak(
                unlimited_output,
                limited_output,
                peak_limit=0.92,
            )
            shutil.copy2(final_output, options.output_dir / "final.wav")
            final_output = options.output_dir / "final.wav"
            metrics["final_safety_limiter_seconds"] = time.perf_counter() - step_start
        except Exception as exc:
            metrics["limiter_used"] = False
            metrics["final_safety_limiter_error"] = str(exc)

    final_mp3 = None
    dry_vocal_mp3 = None
    if preset.output_mp3:
        update("导出 MP3", 96)
        step_start = time.perf_counter()
        final_mp3 = export_mp3(final_output, options.output_dir / "final.mp3")
        metrics["mp3_export_seconds"] = time.perf_counter() - step_start
        step_start = time.perf_counter()
        dry_vocal_mp3 = export_mp3(dry_vocal_output, options.output_dir / "dry_vocal.mp3")
        metrics["dry_vocal_mp3_export_seconds"] = time.perf_counter() - step_start

    update("生成诊断报告", 98)
    diagnostics = analyze_generation(
        AnalyzerContext(
            source_vocal=diagnostic_source_vocal,
            converted_vocal=raw_converted_vocal,
            polished_vocal=converted_vocal,
            final_mix=final_output,
            backing_track=backing_track,
            active_ratio=metrics["active_ratio"] if isinstance(metrics["active_ratio"], float) else None,
        )
    )
    metrics["diagnostics"] = diagnostics
    try:
        final_track = diagnostics["results"][0]["tracks"]["final_mix"]
        metrics["final_peak_after"] = final_track.get("peak")
        metrics["clipping_prevented"] = bool(options.enable_safe_limiter and not final_track.get("clipping_ratio"))
    except (KeyError, IndexError, TypeError, AttributeError):
        pass

    metrics["total_seconds"] = time.perf_counter() - total_start
    metrics["output_wav"] = str(final_output)
    metrics["output_mp3"] = str(final_mp3) if final_mp3 else None
    metrics["output_dry_vocal_mp3"] = str(dry_vocal_mp3) if dry_vocal_mp3 else None
    metrics_path = options.output_dir / "metrics.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        history_dir = archive_generation_history(
            options.output_dir,
            metrics,
            voice_profile_id=voice_profile.id if voice_profile else options.voice_profile_id,
            voice_profile_name=voice_profile.name if voice_profile else options.voice_name,
            song_id=song_record.id if song_record else options.song_id,
            song_title=song_record.title if song_record else options.song_title,
            engine_id=options.engine_id,
            render_mode=options.render_mode,
        )
        metrics["history_dir"] = str(history_dir)
        metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        (history_dir / "metrics.json").write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        metrics["history_error"] = str(exc)
        metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return final_output
