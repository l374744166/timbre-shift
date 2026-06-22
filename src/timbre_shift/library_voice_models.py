"""Trained voice model records."""

from __future__ import annotations

import json
from pathlib import Path

from .library_common import make_id, utc_now
from .library_db import DEFAULT_DB_PATH, connect, init_library
from .library_models import VoiceModel
from .library_rows import voice_model_from_row as _voice_model_from_row
from .library_voices import get_voice_profile


def create_voice_model_record(
    voice_id: str,
    engine_id: str,
    model_name: str,
    model_path: Path,
    index_path: Path | None = None,
    config_path: Path | None = None,
    dataset_path: Path | None = None,
    training_seconds: float | None = None,
    dataset_seconds: float | None = None,
    status: str = "ready",
    metadata: dict[str, object] | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    model_id: str | None = None,
) -> VoiceModel:
    profile = get_voice_profile(voice_id, db_path=db_path)
    if not profile.allowed_as_target:
        raise PermissionError("这个音色没有授权为目标音色，不能创建训练模型")
    init_library(db_path)
    now = utc_now()
    record = VoiceModel(
        id=model_id or make_id("model"),
        voice_id=voice_id,
        engine_id=engine_id,
        model_name=model_name,
        model_path=str(model_path),
        index_path=str(index_path) if index_path else None,
        config_path=str(config_path) if config_path else None,
        dataset_path=str(dataset_path) if dataset_path else None,
        training_seconds=training_seconds,
        dataset_seconds=dataset_seconds,
        status=status,
        created_at=now,
        updated_at=now,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
    )
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO voice_models (
                id, voice_id, engine_id, model_name, model_path, index_path,
                config_path, dataset_path, training_seconds, dataset_seconds,
                status, created_at, updated_at, metadata_json, archived
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.voice_id,
                record.engine_id,
                record.model_name,
                record.model_path,
                record.index_path,
                record.config_path,
                record.dataset_path,
                record.training_seconds,
                record.dataset_seconds,
                record.status,
                record.created_at,
                record.updated_at,
                record.metadata_json,
                int(record.archived),
            ),
        )
    return record


def list_voice_models(
    voice_id: str,
    engine_id: str | None = None,
    include_archived: bool = False,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[VoiceModel]:
    init_library(db_path)
    clauses = ["voice_id = ?"]
    params: list[object] = [voice_id]
    if engine_id:
        clauses.append("engine_id = ?")
        params.append(engine_id)
    if not include_archived:
        clauses.append("archived = 0")
    where = " AND ".join(clauses)
    with connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM voice_models WHERE {where} ORDER BY updated_at DESC",
            params,
        ).fetchall()
    return [_voice_model_from_row(row) for row in rows]


def get_voice_model(
    voice_id: str,
    engine_id: str = "rvc_mlx",
    db_path: Path = DEFAULT_DB_PATH,
) -> VoiceModel | None:
    init_library(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM voice_models
            WHERE voice_id = ? AND engine_id = ? AND status = 'ready' AND archived = 0
            ORDER BY updated_at DESC LIMIT 1
            """,
            (voice_id, engine_id),
        ).fetchone()
    return _voice_model_from_row(row) if row else None


def get_voice_model_by_id(
    model_id: str,
    voice_id: str | None = None,
    engine_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> VoiceModel:
    init_library(db_path)
    clauses = ["id = ?", "archived = 0"]
    params: list[object] = [model_id]
    if voice_id:
        clauses.append("voice_id = ?")
        params.append(voice_id)
    if engine_id:
        clauses.append("engine_id = ?")
        params.append(engine_id)
    with connect(db_path) as conn:
        row = conn.execute(
            f"SELECT * FROM voice_models WHERE {' AND '.join(clauses)}",
            params,
        ).fetchone()
    if not row:
        raise KeyError(f"Voice model not found: {model_id}")
    return _voice_model_from_row(row)


def update_voice_model_status(
    model_id: str,
    status: str,
    model_path: Path | None = None,
    index_path: Path | None = None,
    config_path: Path | None = None,
    training_seconds: float | None = None,
    metadata: dict[str, object] | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> VoiceModel:
    init_library(db_path)
    updates = ["status = ?", "updated_at = ?"]
    params: list[object] = [status, utc_now()]
    optional = {
        "model_path": str(model_path) if model_path else None,
        "index_path": str(index_path) if index_path else None,
        "config_path": str(config_path) if config_path else None,
        "training_seconds": training_seconds,
        "metadata_json": json.dumps(metadata, ensure_ascii=False) if metadata is not None else None,
    }
    for column, value in optional.items():
        if value is not None:
            updates.append(f"{column} = ?")
            params.append(value)
    params.append(model_id)
    with connect(db_path) as conn:
        conn.execute(f"UPDATE voice_models SET {', '.join(updates)} WHERE id = ?", params)
        row = conn.execute("SELECT * FROM voice_models WHERE id = ?", (model_id,)).fetchone()
    if not row:
        raise KeyError(f"Voice model not found: {model_id}")
    return _voice_model_from_row(row)


def archive_voice_model(model_id: str, db_path: Path = DEFAULT_DB_PATH) -> None:
    init_library(db_path)
    with connect(db_path) as conn:
        conn.execute("UPDATE voice_models SET archived = 1, updated_at = ? WHERE id = ?", (utc_now(), model_id))
