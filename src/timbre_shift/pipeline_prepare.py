"""Input voice and song preparation for the generation pipeline."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from .audio import middle_start, normalize_audio, probe_duration
from .library import (
    best_voice_reference,
    get_song,
    get_voice_profile,
    save_song_to_library,
    save_voice_to_library,
)
from .pipeline_config import PipelineOptions, RenderPreset

ProgressCallback = Callable[[str, int], None]


def prepare_voice_reference(
    *,
    options: PipelineOptions,
    preset: RenderPreset,
    prepared_dir: Path,
    metrics: dict[str, object],
    update: ProgressCallback,
):
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
    return voice_profile, prepared_voice


def prepare_song_source(
    *,
    options: PipelineOptions,
    preset: RenderPreset,
    prepared_dir: Path,
    metrics: dict[str, object],
    source_mode: str,
    update: ProgressCallback,
):
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

    clip_label = f"{preset.clip_seconds}秒" if preset.clip_seconds else "完整音频"
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
    return song_record, source_mode, prepared_song
