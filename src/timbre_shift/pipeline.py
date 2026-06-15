"""Local demo orchestration for Timbre Shift."""

from __future__ import annotations

import shutil
import sys
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from .audio import (
    concat_audio_files,
    export_mp3,
    middle_start,
    mix_audio,
    normalize_audio,
    polish_vocal,
    probe_duration,
    split_audio_fixed,
)
from .commands import require_binary
from .demucs import separate_vocals
from .diagnostics import AnalyzerContext, analyze_generation
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
from .engines import get_engine
from .pipeline_config import (
    PRESETS,
    EnvironmentReport,
    PipelineOptions,
    RenderPreset,
    resolve_preset,
    seedvc_chunk_settings,
)
from .seed_vc import SeedVCResult, convert_singing_voice_result
from .vocal_segments import compact_for_conversion, restore_compact_vocals

ProgressCallback = Callable[[str, int], None]


_seedvc_chunk_settings = seedvc_chunk_settings


def _convert_seedvc_whole(
    options: PipelineOptions,
    preset: RenderPreset,
    source_vocal: Path,
    prepared_voice: Path,
    converted_dir: Path,
    actual_device: str,
    allow_cpu_fallback: bool,
) -> SeedVCResult:
    return convert_singing_voice_result(
        seed_vc_dir=options.seed_vc_dir,
        source_vocal=source_vocal,
        target_voice=prepared_voice,
        output_dir=converted_dir,
        diffusion_steps=preset.diffusion_steps,
        length_adjust=options.length_adjust,
        inference_cfg_rate=preset.inference_cfg_rate,
        semi_tone_shift=options.semi_tone_shift,
        fp16=options.fp16 if options.fp16 is not None else False,
        device=actual_device,
        target_voice_seconds=preset.reference_seconds,
        cache_dir=options.cache_dir,
        allow_cpu_fallback=allow_cpu_fallback,
    )


def _convert_seedvc_chunked(
    options: PipelineOptions,
    preset: RenderPreset,
    source_vocal: Path,
    prepared_voice: Path,
    converted_dir: Path,
    actual_device: str,
    chunk_seconds: int,
    workers: int,
) -> SeedVCResult:
    duration = probe_duration(source_vocal) or 0
    if duration <= chunk_seconds * 1.25:
        raise ValueError("Audio is too short for chunked Seed-VC conversion")

    chunk_dir = converted_dir / f"chunks_{chunk_seconds}s"
    input_dir = chunk_dir / "input"
    output_root = chunk_dir / "output"
    chunks = split_audio_fixed(source_vocal, input_dir, chunk_seconds)
    if len(chunks) < 2:
        raise ValueError("Seed-VC chunking produced fewer than two chunks")

    worker_count = min(max(1, workers), len(chunks))
    results: list[SeedVCResult | None] = [None] * len(chunks)

    def convert_one(index: int, chunk: Path) -> tuple[int, SeedVCResult]:
        result = convert_singing_voice_result(
            seed_vc_dir=options.seed_vc_dir,
            source_vocal=chunk,
            target_voice=prepared_voice,
            output_dir=output_root / f"chunk_{index:04d}",
            diffusion_steps=preset.diffusion_steps,
            length_adjust=options.length_adjust,
            inference_cfg_rate=preset.inference_cfg_rate,
            semi_tone_shift=options.semi_tone_shift,
            fp16=options.fp16 if options.fp16 is not None else False,
            device=actual_device,
            target_voice_seconds=preset.reference_seconds,
            cache_dir=options.cache_dir,
            allow_cpu_fallback=False,
        )
        return index, result

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(convert_one, index, chunk) for index, chunk in enumerate(chunks)]
        for future in as_completed(futures):
            index, result = future.result()
            results[index] = result

    ordered = [result for result in results if result is not None]
    if len(ordered) != len(chunks):
        raise RuntimeError("Seed-VC chunked conversion did not finish all chunks")

    output = concat_audio_files(
        [result.output for result in ordered],
        converted_dir / f"converted_chunked_{chunk_seconds}s.wav",
    )
    elapsed = time.perf_counter() - start
    return SeedVCResult(
        output=output,
        cache_hit=all(result.cache_hit for result in ordered),
        elapsed_seconds=elapsed,
        cache_key="chunked-" + "-".join(result.cache_key[:8] for result in ordered),
        device_requested=actual_device,
        device_used=actual_device,
        cpu_fallback_used=False,
    )


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
        update(f"分离人声和伴奏（{preset.demucs_model}）", 30)
        separation = separate_vocals(
            prepared_song,
            output_dir=separated_dir,
            model=preset.demucs_model,
            cache_dir=options.cache_dir,
            overlap=preset.demucs_overlap,
            shifts=preset.demucs_shifts,
        )
        metrics["demucs_seconds"] = time.perf_counter() - step_start
        if not separation.vocals.exists() or not separation.backing.exists():
            raise FileNotFoundError(f"Demucs output not found under {separated_dir}")
        source_vocal = separation.vocals
        backing_track = separation.backing
        cache_label = "命中缓存" if separation.from_cache else "新分离"
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
                preset.demucs_model,
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
        engine_result = engine.convert(
            source_vocal=source_vocal,
            target_voice_or_model=Path(voice_model.model_path),
            output_dir=converted_dir / options.engine_id,
            options={
                "cache_dir": options.cache_dir,
                "index_path": voice_model.index_path,
                "voice_model_id": voice_model.id,
            },
        )
        converted_vocal = engine_result.converted_vocal_path
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
    if options.polish_converted_vocal:
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
        )
        metrics["mix_seconds"] = time.perf_counter() - step_start

    final_mp3 = None
    if preset.output_mp3:
        update("导出 MP3", 96)
        step_start = time.perf_counter()
        final_mp3 = export_mp3(final_output, options.output_dir / "final.mp3")
        metrics["mp3_export_seconds"] = time.perf_counter() - step_start

    update("生成诊断报告", 98)
    metrics["diagnostics"] = analyze_generation(
        AnalyzerContext(
            source_vocal=diagnostic_source_vocal,
            converted_vocal=raw_converted_vocal,
            polished_vocal=converted_vocal,
            final_mix=final_output,
            backing_track=backing_track,
            active_ratio=metrics["active_ratio"] if isinstance(metrics["active_ratio"], float) else None,
        )
    )

    metrics["total_seconds"] = time.perf_counter() - total_start
    metrics["output_wav"] = str(final_output)
    metrics["output_mp3"] = str(final_mp3) if final_mp3 else None
    metrics_path = options.output_dir / "metrics.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return final_output
