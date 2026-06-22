"""SQLite row serializers for library records."""

from __future__ import annotations

import sqlite3

from .library_models import SongRecord, VoiceModel, VoiceProfile, VoiceSample

def voice_from_row(row: sqlite3.Row) -> VoiceProfile:
    return VoiceProfile(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        source_type=row["source_type"],
        rights_status=row["rights_status"],
        allowed_as_target=bool(row["allowed_as_target"]),
        raw_audio_path=row["raw_audio_path"],
        ref_8s_path=row["ref_8s_path"],
        ref_16s_path=row["ref_16s_path"],
        ref_20s_path=row["ref_20s_path"],
        ref_25s_path=row["ref_25s_path"],
        preview_mp3_path=row["preview_mp3_path"],
        sha256=row["sha256"],
        duration_seconds=row["duration_seconds"],
        sample_rate=row["sample_rate"],
        channels=row["channels"],
        source_song_id=row["source_song_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        archived=bool(row["archived"]),
    )


def song_from_row(row: sqlite3.Row) -> SongRecord:
    return SongRecord(
        id=row["id"],
        title=row["title"],
        artist=row["artist"],
        original_audio_path=row["original_audio_path"],
        prepared_audio_path=row["prepared_audio_path"],
        vocals_path=row["vocals_path"],
        no_vocals_path=row["no_vocals_path"],
        demucs_model=row["demucs_model"],
        demucs_cache_key=row["demucs_cache_key"],
        sha256=row["sha256"],
        duration_seconds=row["duration_seconds"],
        sample_rate=row["sample_rate"],
        channels=row["channels"],
        source_kind=row["source_kind"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        archived=bool(row["archived"]),
    )


def voice_sample_from_row(row: sqlite3.Row) -> VoiceSample:
    return VoiceSample(
        id=row["id"],
        voice_id=row["voice_id"],
        name=row["name"],
        raw_audio_path=row["raw_audio_path"],
        clean_audio_path=row["clean_audio_path"],
        source_type=row["source_type"],
        sha256=row["sha256"],
        duration_seconds=row["duration_seconds"],
        sample_rate=row["sample_rate"],
        channels=row["channels"],
        quality_score=row["quality_score"],
        noise_score=row["noise_score"],
        notes=row["notes"],
        created_at=row["created_at"],
        archived=bool(row["archived"]),
    )


def voice_model_from_row(row: sqlite3.Row) -> VoiceModel:
    return VoiceModel(
        id=row["id"],
        voice_id=row["voice_id"],
        engine_id=row["engine_id"],
        model_name=row["model_name"],
        model_path=row["model_path"],
        index_path=row["index_path"],
        config_path=row["config_path"],
        dataset_path=row["dataset_path"],
        training_seconds=row["training_seconds"],
        dataset_seconds=row["dataset_seconds"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        metadata_json=row["metadata_json"],
        archived=bool(row["archived"]),
    )

