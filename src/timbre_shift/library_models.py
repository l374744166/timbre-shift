"""Library record models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceProfile:
    id: str
    name: str
    description: str | None
    source_type: str
    rights_status: str
    allowed_as_target: bool
    raw_audio_path: str
    ref_8s_path: str | None
    ref_16s_path: str | None
    ref_20s_path: str | None
    ref_25s_path: str | None
    preview_mp3_path: str | None
    sha256: str
    duration_seconds: float | None
    sample_rate: int | None
    channels: int | None
    source_song_id: str | None
    created_at: str
    updated_at: str
    archived: bool = False


@dataclass(frozen=True)
class VoiceSample:
    id: str
    voice_id: str
    name: str | None
    raw_audio_path: str
    clean_audio_path: str | None
    source_type: str
    sha256: str
    duration_seconds: float | None
    sample_rate: int | None
    channels: int | None
    quality_score: float | None
    noise_score: float | None
    notes: str | None
    created_at: str
    archived: bool = False


@dataclass(frozen=True)
class VoiceModel:
    id: str
    voice_id: str
    engine_id: str
    model_name: str
    model_path: str
    index_path: str | None
    config_path: str | None
    dataset_path: str | None
    training_seconds: float | None
    dataset_seconds: float | None
    status: str
    created_at: str
    updated_at: str
    metadata_json: str | None
    archived: bool = False


@dataclass(frozen=True)
class SongRecord:
    id: str
    title: str
    artist: str | None
    original_audio_path: str
    prepared_audio_path: str | None
    vocals_path: str | None
    no_vocals_path: str | None
    demucs_model: str | None
    demucs_cache_key: str | None
    sha256: str
    duration_seconds: float | None
    sample_rate: int | None
    channels: int | None
    source_kind: str
    created_at: str
    updated_at: str
    archived: bool = False
