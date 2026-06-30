"""Local demo orchestration for Timbre Shift."""

from __future__ import annotations

import shutil
import sys
import json
import time
from pathlib import Path
from typing import Callable

from .audio import (
    export_mp3,
    limit_audio_peak,
    middle_start,
    mix_audio,
    normalize_audio,
    polish_vocal,
    probe_duration,
)
from .commands import require_binary
from .separation import separate_vocals_smart as separate_vocals
from .diagnostics import AnalyzerContext, analyze_generation
from .generation_history import archive_generation_history
from .library import (
    best_voice_reference,
    get_voice_model,
    get_voice_model_by_id,
    get_song,
    get_voice_profile,
    save_song_to_library,
    save_voice_to_library,
    update_song_stems,
)
from .mix_styles import get_mix_style
from .engines import get_engine
from .pipeline_config import (
    PRESETS,
    EnvironmentReport,
    PipelineOptions,
    resolve_preset,
    seedvc_chunk_settings,
)
from .rvc_presets import get_rvc_preset
from .source_vocal_quality import analyze_source_vocal_quality
from .pre_rvc_cleanup import preprocess_source_vocal_for_rvc
from .pre_rvc_repair import repair_source_vocal_before_rvc
from .pipeline_rvc import (
    _postprocess_rvc_vocal,
    _render_ai_source_repair_variant,
    _render_localized_repair_variant,
    _render_rvc_variants,
)
from .pipeline_seedvc import _convert_seedvc_chunked, _convert_seedvc_whole
from .vocal_segments import compact_for_conversion, map_compact_problem_segments, restore_compact_vocals

ProgressCallback = Callable[[str, int], None]


_seedvc_chunk_settings = seedvc_chunk_settings


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


def _string_attr(value: object, name: str, default: str) -> str:
    attr = getattr(value, name, default)
    return attr if isinstance(attr, str) else default


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
    if not options.voice_profile_id and (not options.voice or not options.voice.exists()):
        raise FileNotFoundError(f"Voice reference not found: {options.voice}")
    if not options.song_id and (not options.song or not options.song.exists()):
        raise FileNotFoundError(f"Song not found: {options.song}")
    if not (options.seed_vc_dir / "inference.py").exists():
        raise FileNotFoundError(f"Seed-VC inference.py not found in: {options.seed_vc_dir}")


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
    metrics: dict[str, object] = {
        "voice_profile_id": options.voice_profile_id,
        "voice_profile_name": None,
        "song_id": options.song_id,
        "song_title": None,
        "render_mode": options.render_mode,
        "source_mode": options.source_mode,
        "engine_id": options.engine_id,
        "engine_name": None,
        "engine_requires_training": False,
        "engine_available": False,
        "voice_model_id": options.voice_model_id,
        "library_voice_hit": False,
        "library_song_stems_hit": False,
        "demucs_cache_hit": False,
        "separation_mode": options.separation_mode,
        "separation_engine": None,
        "separation_fallback_used": False,
        "separation_fallback_reason": None,
        "seedvc_cache_hit": False,
        "rvc_mlx_cache_hit": False,
        "rvc_mlx_model_path": None,
        "rvc_mlx_dataset_seconds": None,
        "rvc_mlx_index_path": None,
        "rvc_mlx_status": None,
        "trained_model_cache_hit": False,
        "trained_model_path": None,
        "trained_model_dataset_seconds": None,
        "trained_model_index_path": None,
        "trained_model_status": None,
        "rvc_preset": options.rvc_preset,
        "rvc_index_rate": 0.0,
        "rvc_protect": None,
        "rvc_f0_method": None,
        "rvc_clean_audio": None,
        "allow_experimental_index": options.allow_experimental_index,
        "applio_crashed": False,
        "applio_crash_signal": None,
        "applio_index_fallback_used": False,
        "diction_mode": options.diction_mode,
        "consonant_blend": None,
        "diction_seconds": 0.0,
        "vocal_style": options.vocal_style,
        "style_postprocess_seconds": 0.0,
        "safe_limiter_enabled": options.enable_safe_limiter,
        "pre_rvc_cleanup_mode": options.pre_rvc_cleanup_mode,
        "pre_rvc_cleanup_seconds": 0.0,
        "pre_rvc_cleanup_output": None,
        "source_vocal_quality_enabled": options.source_vocal_quality_enabled,
        "source_quality_score": None,
        "source_quality_summary": None,
        "source_problem_segment_count": 0,
        "source_problem_segments": [],
        "source_has_clipping": False,
        "source_high_freq_risk": False,
        "source_harshness_risk": False,
        "source_quality_metrics_path": None,
        "source_quality_error": None,
        "pre_rvc_repair_mode": options.pre_rvc_cleanup_mode,
        "pre_rvc_repair_used": False,
        "pre_rvc_repair_seconds": 0.0,
        "pre_rvc_repair_output": None,
        "problem_segments_repaired": 0,
        "deharsh_mode": options.deharsh_mode,
        "deharsh_used": False,
        "deharsh_seconds": 0.0,
        "auto_repair_variant_generated": False,
        "auto_repair_reason": None,
        "converted_harshness_score": None,
        "mix_style": options.mix_style,
        "vocal_gain": None,
        "backing_gain": None,
        "limiter_used": options.enable_safe_limiter,
        "final_safety_limit": 0.92 if options.enable_safe_limiter else None,
        "final_safety_limiter_seconds": 0.0,
        "final_unlimited_wav": None,
        "final_peak_before": None,
        "final_peak_after": None,
        "clipping_prevented": False,
        "generate_variants_requested": bool(options.generate_variants),
        "variants": [],
        "seedvc_chunked_attempted": False,
        "seedvc_chunked_used": False,
        "seedvc_chunk_seconds": 0,
        "seedvc_chunk_workers": 1,
        "seedvc_chunk_error": None,
        "song_duration_seconds": None,
        "active_vocal_seconds": None,
        "active_ratio": None,
        "prepare_voice_seconds": 0.0,
        "prepare_song_seconds": 0.0,
        "demucs_seconds": 0.0,
        "vocal_segment_detect_seconds": 0.0,
        "seedvc_seconds": 0.0,
        "restore_timeline_seconds": 0.0,
        "vocal_polish_seconds": 0.0,
        "vocal_polish_enabled": options.polish_converted_vocal,
        "vocal_polish_chain": None,
        "converted_vocal_wav": None,
        "polished_vocal_wav": None,
        "mix_seconds": 0.0,
        "mp3_export_seconds": 0.0,
        "total_seconds": 0.0,
        "seedvc_rtf": None,
        "mps_requested": False,
        "mps_used": False,
        "seedvc_device": None,
        "seedvc_cpu_fallback_used": False,
        "convert_seconds": 0.0,
        "output_wav": None,
        "output_mp3": None,
        "diagnostics": None,
        "error_message": None,
    }

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

    clip_label = f"{preset.clip_seconds}秒" if preset.clip_seconds else "完整音频"
    voice_profile = None
    step_start = time.perf_counter()
    if options.voice_profile_id:
        update("读取本地音色库", 8)
        voice_profile = get_voice_profile(options.voice_profile_id, db_path=options.library_db_path)
        if not voice_profile.allowed_as_target:
            raise PermissionError("这个音色没有授权为目标音色，不能用于换声")
        metrics["library_voice_hit"] = True
        metrics["voice_profile_name"] = voice_profile.name
        prepared_voice = best_voice_reference(voice_profile, preset.reference_seconds)
        if not prepared_voice.exists():
            raise FileNotFoundError(f"Voice reference not found: {prepared_voice}")
    elif options.save_voice_to_library:
        update("保存声音样本到本地音色库", 8)
        if not options.voice:
            raise FileNotFoundError("Voice reference not found")
        voice_profile = save_voice_to_library(
            input_audio=options.voice,
            name=options.voice_name or options.voice.stem,
            description=options.voice_description,
            source_type="upload_voice",
            rights_status="own_voice" if options.rights_confirmed else "unknown",
            allowed_as_target=options.rights_confirmed,
            library_dir=options.library_dir,
            db_path=options.library_db_path,
        )
        if voice_profile.allowed_as_target:
            prepared_voice = best_voice_reference(voice_profile, preset.reference_seconds)
        else:
            prepared_voice = normalize_audio(
                options.voice,
                prepared_dir / "target_voice.wav",
                duration_seconds=preset.reference_seconds,
                start_seconds=middle_start(options.voice, preset.reference_seconds),
            )
    else:
        update(f"处理声音样本（最多{preset.reference_seconds}秒）", 8)
        if not options.voice:
            raise FileNotFoundError("Voice reference not found")
        prepared_voice = normalize_audio(
            options.voice,
            prepared_dir / "target_voice.wav",
            duration_seconds=preset.reference_seconds,
            start_seconds=middle_start(options.voice, preset.reference_seconds),
        )
    metrics["prepare_voice_seconds"] = time.perf_counter() - step_start

    song_record = None
    source_mode = options.source_mode
    step_start = time.perf_counter()
    if options.song_id:
        update("读取本地歌曲库", 15)
        song_record = get_song(options.song_id, db_path=options.library_db_path)
        metrics["song_title"] = song_record.title
        source_mode = "clean_vocal" if song_record.source_kind == "clean_vocal" else "full_song"
        song_source = Path(song_record.prepared_audio_path or song_record.original_audio_path)
        if not song_source.exists():
            raise FileNotFoundError(f"Song not found: {song_source}")
    elif options.save_song_to_library:
        update("保存歌曲到本地歌曲库", 15)
        if not options.song:
            raise FileNotFoundError("Song not found")
        song_record = save_song_to_library(
            input_audio=options.song,
            title=options.song_title or options.song.stem,
            artist=options.song_artist,
            source_kind="clean_vocal" if options.skip_separation or source_mode == "clean_vocal" else "full_song",
            library_dir=options.library_dir,
            db_path=options.library_db_path,
        )
        song_source = Path(song_record.prepared_audio_path or song_record.original_audio_path)
    else:
        if not options.song:
            raise FileNotFoundError("Song not found")
        song_source = options.song

    skip_separation = options.skip_separation or source_mode in {"clean_vocal", "clean_vocal_only"}
    update(f"处理歌曲文件（{preset.name} / {clip_label}）", 20)
    if options.song_id and preset.clip_seconds is None and song_record and song_record.prepared_audio_path:
        prepared_song = Path(song_record.prepared_audio_path)
    else:
        prepared_song = normalize_audio(
            song_source,
            prepared_dir / "song.wav",
            duration_seconds=preset.clip_seconds,
            start_seconds=middle_start(song_source, preset.clip_seconds),
        )
    metrics["prepare_song_seconds"] = time.perf_counter() - step_start
    metrics["song_duration_seconds"] = probe_duration(prepared_song)

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
    if engine.requires_training:
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

    update(f"转换为目标音色（{engine.name}，{cache_label}）", 70)
    if options.engine_id == "seedvc":
        allow_cpu_fallback = preset.clip_seconds is not None and preset.clip_seconds <= 15
        chunk_seconds, chunk_workers = _seedvc_chunk_settings(options, preset)
        metrics["seedvc_chunk_seconds"] = chunk_seconds
        metrics["seedvc_chunk_workers"] = chunk_workers
        seedvc_result = None
        if chunk_seconds:
            metrics["seedvc_chunked_attempted"] = True
            try:
                update(f"分段换声（{chunk_seconds}秒 / {chunk_workers}路）", 70)
                seedvc_result = _convert_seedvc_chunked(
                    options=options,
                    preset=preset,
                    source_vocal=source_vocal,
                    prepared_voice=prepared_voice,
                    converted_dir=converted_dir,
                    actual_device=actual_device,
                    chunk_seconds=chunk_seconds,
                    workers=chunk_workers,
                )
                metrics["seedvc_chunked_used"] = True
            except Exception as exc:
                metrics["seedvc_chunk_error"] = str(exc)
                update("分段换声失败，回退整段换声", 70)

        if seedvc_result is None:
            seedvc_result = _convert_seedvc_whole(
                options=options,
                preset=preset,
                source_vocal=source_vocal,
                prepared_voice=prepared_voice,
                converted_dir=converted_dir,
                actual_device=actual_device,
                allow_cpu_fallback=allow_cpu_fallback,
            )
        converted_vocal = seedvc_result.output
        metrics["seedvc_cache_hit"] = seedvc_result.cache_hit
        metrics["seedvc_seconds"] = seedvc_result.elapsed_seconds
        metrics["seedvc_device"] = seedvc_result.device_used
        metrics["mps_used"] = seedvc_result.device_used == "mps"
        metrics["seedvc_cpu_fallback_used"] = seedvc_result.cpu_fallback_used
        metrics["convert_seconds"] = seedvc_result.elapsed_seconds
    elif engine.requires_training:
        if not voice_profile:
            raise ValueError(f"{engine.name} 需要选择一个已保存音色")
        if options.voice_model_id:
            voice_model = get_voice_model_by_id(
                options.voice_model_id,
                voice_id=voice_profile.id,
                engine_id=options.engine_id,
                db_path=options.library_db_path,
            )
            if voice_model.status != "ready":
                raise FileNotFoundError(f"选择的 {engine.name} 模型还没有准备好。")
        else:
            voice_model = get_voice_model(voice_profile.id, engine_id=options.engine_id, db_path=options.library_db_path)
        if not voice_model:
            raise FileNotFoundError(f"{engine.name} 模型不存在，请先准备数据并训练。")
        metrics["voice_model_id"] = voice_model.id
        if not engine.is_available():
            missing = ", ".join(str(item) for item in engine_check.get("missing", []))
            raise RuntimeError(f"{engine.name} 未安装或未配置：{missing}")
        metrics["trained_model_path"] = voice_model.model_path
        metrics["trained_model_dataset_seconds"] = voice_model.dataset_seconds
        metrics["trained_model_index_path"] = voice_model.index_path
        metrics["trained_model_status"] = voice_model.status
        if options.engine_id == "rvc_mlx":
            metrics["rvc_mlx_model_path"] = voice_model.model_path
            metrics["rvc_mlx_dataset_seconds"] = voice_model.dataset_seconds
            metrics["rvc_mlx_index_path"] = voice_model.index_path
            metrics["rvc_mlx_status"] = voice_model.status
        rvc_convert_options = {
            "cache_dir": options.cache_dir,
            "index_path": voice_model.index_path,
            "voice_model_id": voice_model.id,
            "index_rate": effective_rvc_index_rate,
            "protect": rvc_preset.protect,
            "pitch_shift": rvc_preset.pitch,
            "f0_method": rvc_preset.f0_method,
            "clean_audio": rvc_preset.clean_audio,
        }
        engine_result = engine.convert(
            source_vocal=conversion_source_vocal,
            target_voice_or_model=Path(voice_model.model_path),
            output_dir=converted_dir / options.engine_id,
            options=rvc_convert_options,
        )
        converted_vocal = engine_result.converted_vocal_path
        metrics["rvc_index_rate"] = engine_result.metadata.get("index_rate", effective_rvc_index_rate)
        metrics["applio_index_fallback_used"] = bool(engine_result.metadata.get("index_fallback_used"))
        metrics["applio_crashed"] = bool(engine_result.metadata.get("crashed"))
        metrics["applio_crash_signal"] = engine_result.metadata.get("crash_signal")
        metrics["trained_model_cache_hit"] = engine_result.cache_hit
        if options.engine_id == "rvc_mlx":
            metrics["rvc_mlx_cache_hit"] = engine_result.cache_hit
        metrics["convert_seconds"] = engine_result.seconds
        metrics["seedvc_device"] = engine_result.device
        metrics["mps_used"] = engine_result.device == "mps"
    else:
        raise ValueError(f"Unsupported conversion engine: {options.engine_id}")
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
            if source_risky and "voice_model" in locals() and "rvc_convert_options" in locals():
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
