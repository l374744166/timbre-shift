"""Payload builders for voice, song, and model library actions."""

from __future__ import annotations

from .library import (
    DEFAULT_DB_PATH,
    DEFAULT_LIBRARY_DIR,
    archive_song,
    archive_voice_sample,
    archive_voice_model,
    archive_voice_profile,
    create_empty_voice_profile,
    list_voice_samples,
    refresh_voice_profile_references,
)
from .web_serializers import serialize_voice_sample


def delete_voice_sample_payload(fields: dict[str, object]) -> dict[str, object]:
    voice_id = str(fields.get("voice_profile_id", "")).strip()
    sample_id = str(fields.get("sample_id", "")).strip()
    if not voice_id or not sample_id:
        raise ValueError("请选择要删除的素材")
    archive_voice_sample(sample_id, db_path=DEFAULT_DB_PATH)
    refresh_voice_profile_references(voice_id, library_dir=DEFAULT_LIBRARY_DIR, db_path=DEFAULT_DB_PATH)
    samples = list_voice_samples(voice_id, db_path=DEFAULT_DB_PATH)
    return {
        "message": "素材已删除",
        "sample_count": len(samples),
        "samples": [serialize_voice_sample(sample) for sample in samples],
    }


def delete_voice_payload(fields: dict[str, object]) -> dict[str, object]:
    voice_id = str(fields.get("voice_profile_id", "")).strip()
    if not voice_id:
        raise ValueError("请选择要删除的音色")
    archive_voice_profile(voice_id, db_path=DEFAULT_DB_PATH)
    return {"id": voice_id, "message": "音色已删除"}


def delete_song_payload(fields: dict[str, object]) -> dict[str, object]:
    song_id = str(fields.get("song_id", "")).strip()
    if not song_id:
        raise ValueError("请选择要删除的歌曲")
    archive_song(song_id, db_path=DEFAULT_DB_PATH)
    return {"id": song_id, "message": "歌曲已删除"}


def delete_voice_model_payload(fields: dict[str, object]) -> dict[str, object]:
    model_id = str(fields.get("voice_model_id", "")).strip()
    if not model_id:
        raise ValueError("请选择要删除的模型")
    archive_voice_model(model_id, db_path=DEFAULT_DB_PATH)
    return {"id": model_id, "message": "模型已删除"}


def create_voice_profile_payload(fields: dict[str, object]) -> dict[str, object]:
    voice_name = str(fields.get("voice_name", "")).strip() or "未命名音色库"
    profile = create_empty_voice_profile(
        name=voice_name,
        description="RVC training library",
        library_dir=DEFAULT_LIBRARY_DIR,
        db_path=DEFAULT_DB_PATH,
    )
    return {
        "id": profile.id,
        "name": profile.name,
        "source_type": profile.source_type,
        "sample_count": 0,
        "added_count": 0,
        "message": "音色库已创建，请添加训练素材",
    }
