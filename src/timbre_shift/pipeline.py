"""Local demo orchestration for Timbre Shift."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Callable

from .audio import (
    polish_vocal,
    probe_duration,
)
from .pipeline_environment import (
    check_pipeline_environment as check_environment,
    validate_pipeline_inputs as validate_inputs,
)
from .separation import separate_vocals_smart as separate_vocals
from .library import (
    update_song_stems,
)
from .mix_styles import get_mix_style
from .engines import get_engine
from .pipeline_metrics import build_initial_metrics
from .pipeline_output import finalize_generation_outputs
from .pipeline_prepare import prepare_song_source, prepare_voice_reference
from .pipeline_config import (
    PRESETS,
    PipelineOptions,
    resolve_preset,
)
from .rvc_presets import get_rvc_preset
from .pipeline_rvc_flow import postprocess_rvc_output
from .pipeline_conversion import convert_source_vocal
from .pipeline_source import prepare_conversion_source_vocal
from .vocal_segments import compact_for_conversion, restore_compact_vocals

ProgressCallback = Callable[[str, int], None]



def _string_attr(value: object, name: str, default: str) -> str:
    attr = getattr(value, name, default)
    return attr if isinstance(attr, str) else default


def _copy_library_stems(song_id: str, vocals: Path, backing: Path, library_dir: Path) -> tuple[Path, Path]:
    song_dir = library_dir / "songs" / song_id
    song_dir.mkdir(parents=True, exist_ok=True)
    library_vocals = song_dir / "vocals.wav"
    library_backing = song_dir / "no_vocals.wav"
    shutil.copy2(vocals, library_vocals)
    shutil.copy2(backing, library_backing)
    return library_vocals, library_backing


def run_demo(options: PipelineOptions, progress: ProgressCallback | None = None) -> Path:
    def update(step: str, percent: int) -> None:
        if progress:
            progress(step, percent)

    total_start = time.perf_counter()
    stale_variants_dir = options.output_dir / "variants"
    if stale_variants_dir.exists():
        shutil.rmtree(stale_variants_dir)
    metrics = build_initial_metrics(options)

    update("检查输入文件", 3)
    validate_inputs(options)
    preset = resolve_preset(options)
    engine = get_engine(options.engine_id)
    engine_check = engine.check()
    metrics["engine_name"] = engine.name
    metrics["engine_requires_training"] = engine.requires_training
    metrics["engine_available"] = bool(engine_check.get("available"))
    actual_device = options.device or preset.device
    metrics["mps_requested"] = actual_device == "mps"
    rvc_preset = get_rvc_preset(options.rvc_preset, options.allow_experimental_index)
    requested_diction_mode = options.diction_mode or rvc_preset.diction_mode
    requested_vocal_style = options.vocal_style or rvc_preset.vocal_style
    metrics["rvc_preset"] = rvc_preset.id
    metrics["diction_mode"] = requested_diction_mode
    metrics["vocal_style"] = requested_vocal_style
    metrics["rvc_index_rate"] = rvc_preset.index_rate
    metrics["rvc_protect"] = rvc_preset.protect
    metrics["rvc_f0_method"] = rvc_preset.f0_method
    metrics["rvc_clean_audio"] = rvc_preset.clean_audio
    effective_rvc_index_rate = (
        float(options.rvc_index_rate)
        if options.allow_experimental_index and options.rvc_index_rate is not None
        else rvc_preset.index_rate
    )
    metrics["rvc_index_rate"] = effective_rvc_index_rate
    mix_style = get_mix_style(options.mix_style)
    metrics["mix_style"] = mix_style.id
    metrics["vocal_gain"] = mix_style.vocal_gain
    metrics["backing_gain"] = mix_style.backing_gain

    prepared_dir = options.work_dir / "prepared" / options.render_mode
    separated_dir = options.work_dir / "separated" / options.render_mode
    converted_dir = options.work_dir / "converted" / options.render_mode

    voice_profile, prepared_voice = prepare_voice_reference(
        options=options,
        preset=preset,
        prepared_dir=prepared_dir,
        metrics=metrics,
        update=update,
    )

    source_mode = options.source_mode
    song_record, source_mode, prepared_song = prepare_song_source(
        options=options,
        preset=preset,
        prepared_dir=prepared_dir,
        metrics=metrics,
        source_mode=source_mode,
        update=update,
    )

    skip_separation = options.skip_separation or source_mode in {"clean_vocal", "clean_vocal_only"}
    if skip_separation:
        update("使用已分离人声，跳过歌曲分离", 30)
        source_vocal = prepared_song
        backing_track = None
        cache_label = "跳过分离"
        compact_result = None
    elif (
        song_record
        and preset.clip_seconds is None
        and song_record.vocals_path
        and song_record.no_vocals_path
        and Path(song_record.vocals_path).exists()
        and Path(song_record.no_vocals_path).exists()
    ):
        update("复用本地歌曲库分离结果", 30)
        source_vocal = Path(song_record.vocals_path)
        backing_track = Path(song_record.no_vocals_path)
        cache_label = "歌曲库命中"
        metrics["library_song_stems_hit"] = True
        compact_result = None
    else:
        step_start = time.perf_counter()
        separation_mode_label = {
            "standard": "标准分离",
            "demucs_high_quality": "高质量分离",
            "demucs_max_quality": "最高质量分离",
            "ai_tolerant": "AI歌容错分离",
        }.get(options.separation_mode, "标准分离")
        update(f"分离人声和伴奏（{separation_mode_label}）", 30)
        separation = separate_vocals(
            prepared_song,
            output_dir=separated_dir,
            mode=options.separation_mode,
            model=preset.demucs_model,
            cache_dir=options.cache_dir,
            overlap=preset.demucs_overlap,
            shifts=preset.demucs_shifts,
        )
        metrics["demucs_seconds"] = time.perf_counter() - step_start
        metrics["separation_mode"] = _string_attr(separation, "mode", options.separation_mode)
        metrics["separation_engine"] = _string_attr(separation, "engine", "demucs")
        metrics["separation_fallback_used"] = bool(getattr(separation, "fallback_used", False) is True)
        fallback_reason = getattr(separation, "fallback_reason", None)
        metrics["separation_fallback_reason"] = fallback_reason if isinstance(fallback_reason, str) else None
        if not separation.vocals.exists() or not separation.backing.exists():
            raise FileNotFoundError(f"Separation output not found under {separated_dir}")
        source_vocal = separation.vocals
        backing_track = separation.backing
        cache_label = "命中缓存" if separation.from_cache else "新分离"
        if bool(getattr(separation, "fallback_used", False)):
            cache_label = f"{cache_label}，已回退"
        metrics["demucs_cache_hit"] = separation.from_cache
        compact_result = None
        if song_record and preset.clip_seconds is None:
            library_vocals, library_backing = _copy_library_stems(
                song_record.id,
                separation.vocals,
                separation.backing,
                options.library_dir,
            )
            update_song_stems(
                song_record.id,
                library_vocals,
                library_backing,
                str(metrics.get("separation_engine") or preset.demucs_model),
                cache_label,
                db_path=options.library_db_path,
            )
            source_vocal = library_vocals
            backing_track = library_backing

    if preset.compact_vocals and not skip_separation:
        diagnostic_source_vocal = source_vocal
        step_start = time.perf_counter()
        update("检测有效人声片段", 45)
        compact_result = compact_for_conversion(
            source_vocal,
            prepared_dir / "compact_vocals.wav",
        )
        metrics["vocal_segment_detect_seconds"] = time.perf_counter() - step_start
        metrics["active_vocal_seconds"] = compact_result.active_duration
        metrics["song_duration_seconds"] = compact_result.total_duration
        metrics["active_ratio"] = (
            compact_result.active_duration / compact_result.total_duration
            if compact_result.total_duration
            else None
        )
        if compact_result.active_duration < compact_result.total_duration * 0.92:
            active_seconds = int(round(compact_result.active_duration))
            total_seconds = int(round(compact_result.total_duration))
            update(f"只转换有效人声（{active_seconds}/{total_seconds}秒）", 55)
            source_vocal = compact_result.audio
            cache_label = f"{cache_label}，压缩人声"
        else:
            compact_result = None
            update("人声几乎贯穿全曲，直接转换", 55)
    else:
        diagnostic_source_vocal = source_vocal
    if metrics["active_vocal_seconds"] is None:
        metrics["active_vocal_seconds"] = probe_duration(source_vocal)

    conversion_source_vocal = prepare_conversion_source_vocal(
        options=options,
        engine_requires_training=engine.requires_training,
        source_vocal=source_vocal,
        converted_dir=converted_dir,
        metrics=metrics,
        update=update,
    )

    conversion_result = convert_source_vocal(
        options=options,
        preset=preset,
        engine=engine,
        engine_check=engine_check,
        source_vocal=source_vocal,
        conversion_source_vocal=conversion_source_vocal,
        prepared_voice=prepared_voice,
        converted_dir=converted_dir,
        actual_device=actual_device,
        voice_profile=voice_profile,
        rvc_preset=rvc_preset,
        effective_rvc_index_rate=effective_rvc_index_rate,
        cache_label=cache_label,
        metrics=metrics,
        update=update,
    )
    converted_vocal = conversion_result.converted_vocal
    voice_model = conversion_result.voice_model
    rvc_convert_options = conversion_result.rvc_convert_options
    raw_converted_vocal = converted_vocal
    active_for_rtf = metrics["active_vocal_seconds"] or probe_duration(source_vocal) or 0
    metrics["seedvc_rtf"] = (
        float(metrics["convert_seconds"]) / active_for_rtf
        if active_for_rtf
        else None
    )

    if compact_result is not None:
        step_start = time.perf_counter()
        update("还原人声到原时间线", 86)
        converted_vocal = restore_compact_vocals(
            converted_compact=converted_vocal,
            output=converted_dir / "converted_full_timeline.wav",
            segments=compact_result.segments,
            total_duration=compact_result.total_duration,
        )
        metrics["restore_timeline_seconds"] = time.perf_counter() - step_start

    metrics["converted_vocal_wav"] = str(converted_vocal)
    raw_converted_vocal = converted_vocal
    if options.engine_id == "rvc_applio":
        converted_vocal, raw_converted_vocal = postprocess_rvc_output(
            options=options,
            converted_vocal=converted_vocal,
            source_vocal=source_vocal,
            diagnostic_source_vocal=diagnostic_source_vocal,
            converted_dir=converted_dir,
            metrics=metrics,
            requested_diction_mode=requested_diction_mode,
            requested_vocal_style=requested_vocal_style,
            rvc_preset=rvc_preset,
            backing_track=backing_track,
            mix_style=mix_style,
            compact_result=compact_result,
            engine=engine,
            voice_model=voice_model if "voice_model" in locals() else None,
            rvc_convert_options=rvc_convert_options if "rvc_convert_options" in locals() else None,
            update=update,
        )
    elif options.polish_converted_vocal:
        step_start = time.perf_counter()
        update("优化换声后人声", 90)
        converted_vocal = polish_vocal(
            converted_vocal,
            converted_dir / "converted_optimized.wav",
        )
        metrics["vocal_polish_seconds"] = time.perf_counter() - step_start
        metrics["polished_vocal_wav"] = str(converted_vocal)
        metrics["vocal_polish_chain"] = [
            "去低频浑浊",
            "轻微提高清晰度和空气感",
            "削齿音",
            "压缩动态",
            "限幅防爆",
            "响度统一",
        ]

    final_output = finalize_generation_outputs(
        options=options,
        preset=preset,
        metrics=metrics,
        converted_vocal=converted_vocal,
        raw_converted_vocal=raw_converted_vocal,
        diagnostic_source_vocal=diagnostic_source_vocal,
        backing_track=backing_track,
        mix_style=mix_style,
        voice_profile=voice_profile,
        song_record=song_record,
        total_start=total_start,
        update=update,
    )
    return final_output
