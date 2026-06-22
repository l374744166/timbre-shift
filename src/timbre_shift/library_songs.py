"""Song records and cached stem metadata."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .audio import normalize_audio
from .library_common import _existing_song_by_hash, _metadata_audio_defaults, _write_metadata, make_id, sha256_file, utc_now
from .library_db import DEFAULT_DB_PATH, DEFAULT_LIBRARY_DIR, connect, init_library
from .library_models import SongRecord
from .library_rows import song_from_row as _song_from_row


def create_song_record(
    title: str,
    artist: str | None,
    original_audio_path: Path,
    prepared_audio_path: Path | None,
    sha256: str,
    duration_seconds: float | None = None,
    sample_rate: int | None = None,
    channels: int | None = None,
    source_kind: str = "full_song",
    db_path: Path = DEFAULT_DB_PATH,
    song_id: str | None = None,
) -> SongRecord:
    init_library(db_path)
    now = utc_now()
    record = SongRecord(
        id=song_id or make_id("song"),
        title=title,
        artist=artist,
        original_audio_path=str(original_audio_path),
        prepared_audio_path=str(prepared_audio_path) if prepared_audio_path else None,
        vocals_path=None,
        no_vocals_path=None,
        demucs_model=None,
        demucs_cache_key=None,
        sha256=sha256,
        duration_seconds=duration_seconds,
        sample_rate=sample_rate,
        channels=channels,
        source_kind=source_kind,
        created_at=now,
        updated_at=now,
    )
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO songs (
                id, title, artist, original_audio_path, prepared_audio_path,
                vocals_path, no_vocals_path, demucs_model, demucs_cache_key,
                sha256, duration_seconds, sample_rate, channels, source_kind,
                created_at, updated_at, archived
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.title,
                record.artist,
                record.original_audio_path,
                record.prepared_audio_path,
                record.vocals_path,
                record.no_vocals_path,
                record.demucs_model,
                record.demucs_cache_key,
                record.sha256,
                record.duration_seconds,
                record.sample_rate,
                record.channels,
                record.source_kind,
                record.created_at,
                record.updated_at,
                int(record.archived),
            ),
        )
    return record


def save_song_to_library(
    input_audio: Path,
    title: str,
    artist: str | None = None,
    source_kind: str = "full_song",
    library_dir: Path = DEFAULT_LIBRARY_DIR,
    db_path: Path = DEFAULT_DB_PATH,
) -> SongRecord:
    init_library(db_path)
    file_hash = sha256_file(input_audio)
    existing = _existing_song_by_hash(db_path, file_hash)
    if existing:
        return existing

    song_id = make_id("song")
    song_dir = library_dir / "songs" / song_id
    song_dir.mkdir(parents=True, exist_ok=True)
    original = normalize_audio(input_audio, song_dir / "original.wav")
    prepared = normalize_audio(original, song_dir / "prepared.wav")
    duration, sample_rate, channels = _metadata_audio_defaults(prepared)
    record = create_song_record(
        title=title,
        artist=artist,
        original_audio_path=original,
        prepared_audio_path=prepared,
        sha256=file_hash,
        duration_seconds=duration,
        sample_rate=sample_rate,
        channels=channels,
        source_kind=source_kind,
        db_path=db_path,
        song_id=song_id,
    )
    _write_metadata(song_dir / "metadata.json", asdict(record))
    return record


def list_songs(include_archived: bool = False, db_path: Path = DEFAULT_DB_PATH) -> list[SongRecord]:
    init_library(db_path)
    where = "" if include_archived else "WHERE archived = 0"
    with connect(db_path) as conn:
        rows = conn.execute(f"SELECT * FROM songs {where} ORDER BY updated_at DESC").fetchall()
    return [_song_from_row(row) for row in rows]


def get_song(song_id: str, db_path: Path = DEFAULT_DB_PATH) -> SongRecord:
    init_library(db_path)
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM songs WHERE id = ?", (song_id,)).fetchone()
    if not row:
        raise KeyError(f"Song not found: {song_id}")
    return _song_from_row(row)


def update_song_stems(
    song_id: str,
    vocals_path: Path,
    no_vocals_path: Path,
    demucs_model: str,
    demucs_cache_key: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> SongRecord:
    init_library(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """
            UPDATE songs
            SET vocals_path = ?, no_vocals_path = ?, demucs_model = ?,
                demucs_cache_key = ?, updated_at = ?
            WHERE id = ?
            """,
            (str(vocals_path), str(no_vocals_path), demucs_model, demucs_cache_key, utc_now(), song_id),
        )
    return get_song(song_id, db_path=db_path)


def archive_song(song_id: str, db_path: Path = DEFAULT_DB_PATH) -> None:
    init_library(db_path)
    with connect(db_path) as conn:
        conn.execute("UPDATE songs SET archived = 1, updated_at = ? WHERE id = ?", (utc_now(), song_id))
