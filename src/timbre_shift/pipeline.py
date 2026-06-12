"""Local demo orchestration for Timbre Shift."""

from __future__ import annotations

import shutil
import sys
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from .audio import export_mp3, middle_start, mix_audio, normalize_audio, probe_duration
from .commands import require_binary
from .demucs import separate_vocals
from .library import (
    DEFAULT_DB_PATH,
    DEFAULT_LIBRARY_DIR,
    best_voice_reference,
    get_song,
    get_voice_profile,
    save_song_to_library,
    save_voice_to_library,
    update_song_stems,
)
from .seed_vc import SeedVCResult, convert_singing_voice_result
from .vocal_segments import compact_for_conversion, restore_compact_vocals

ProgressCallback = Callable[[str, int], None]


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
    "m2max_offline_max": RenderPreset("离线最高质量", None, "htdemucs_ft", 0.25, 25, 0.7, 25, False),
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


def resolve_preset(options: PipelineOptions) -> RenderPreset:
    if options.render_mode not in PRESETS:
        available = ", ".join(PRESETS)
        raise ValueError(f"Unknown render_mode={options.render_mode}. Available: {available}")
    base = PRESETS[options.render_mode]
    return RenderPreset(
        name=base.name,
        clip_seconds=options.clip_seconds if options.clip_seconds is not None else base.clip_seconds,
        demucs_model=options.demucs_model or base.demucs_model,
        demucs_overlap=options.demucs_overlap if options.demucs_overlap is not None else base.demucs_overlap,
        diffusion_steps=options.diffusion_steps if options.diffusion_steps is not None else base.diffusion_steps,
        inference_cfg_rate=(
            options.inference_cfg_rate
            if options.inference_cfg_rate is not None
            else base.inference_cfg_rate
        ),
        reference_seconds=(
            options.reference_seconds
            if options.reference_seconds is not None
            else base.reference_seconds
        ),
        compact_vocals=(
            options.compact_vocals
            if options.compact_vocals is not None
            else base.compact_vocals
        ),
        demucs_shifts=base.demucs_shifts,
        device=base.device,
        output_mp3=base.output_mp3,
    )


def run_demo(options: PipelineOptions, progress: Optional[ProgressCallback] = None) -> Path:
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
        "library_voice_hit": False,
        "library_song_stems_hit": False,
        "demucs_cache_hit": False,
        "seedvc_cache_hit": False,
        "song_duration_seconds": None,
        "active_vocal_seconds": None,
        "active_ratio": None,
        "prepare_voice_seconds": 0.0,
        "prepare_song_seconds": 0.0,
        "demucs_seconds": 0.0,
        "vocal_segment_detect_seconds": 0.0,
        "seedvc_seconds": 0.0,
        "restore_timeline_seconds": 0.0,
        "mix_seconds": 0.0,
        "mp3_export_seconds": 0.0,
        "total_seconds": 0.0,
        "seedvc_rtf": None,
        "mps_requested": False,
        "mps_used": False,
        "seedvc_device": None,
        "seedvc_cpu_fallback_used": False,
        "output_wav": None,
        "output_mp3": None,
        "error_message": None,
    }

    update("检查输入文件", 3)
    validate_inputs(options)
    preset = resolve_preset(options)
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
        update("使用干净人声，跳过分离", 30)
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
    if metrics["active_vocal_seconds"] is None:
        metrics["active_vocal_seconds"] = probe_duration(source_vocal)

    update(f"转换为目标音色（{preset.diffusion_steps} steps，{cache_label}）", 70)
    allow_cpu_fallback = preset.clip_seconds is not None and preset.clip_seconds <= 15
    seedvc_result = convert_singing_voice_result(
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
    converted_vocal = seedvc_result.output
    metrics["seedvc_cache_hit"] = seedvc_result.cache_hit
    metrics["seedvc_seconds"] = seedvc_result.elapsed_seconds
    metrics["seedvc_device"] = seedvc_result.device_used
    metrics["mps_used"] = seedvc_result.device_used == "mps"
    metrics["seedvc_cpu_fallback_used"] = seedvc_result.cpu_fallback_used
    active_for_rtf = metrics["active_vocal_seconds"] or probe_duration(source_vocal) or 0
    metrics["seedvc_rtf"] = (
        seedvc_result.elapsed_seconds / active_for_rtf
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

    if backing_track is None:
        update("导出干净人声", 92)
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

    metrics["total_seconds"] = time.perf_counter() - total_start
    metrics["output_wav"] = str(final_output)
    metrics["output_mp3"] = str(final_mp3) if final_mp3 else None
    metrics_path = options.output_dir / "metrics.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return final_output
