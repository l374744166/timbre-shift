"""Local SQLite-backed asset library for voices and songs."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .audio import normalize_audio, probe_duration
from .commands import as_strs, run_command


DEFAULT_LIBRARY_DIR = Path("data/library")
DEFAULT_DB_PATH = DEFAULT_LIBRARY_DIR / "timbre_shift.db"
VOICE_REF_SECONDS = (8, 16, 20, 25)


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


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_id(prefix: str) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}_{uuid4().hex[:8]}"


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_library(db_path: Path = DEFAULT_DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS voices (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                source_type TEXT NOT NULL,
                rights_status TEXT NOT NULL,
                allowed_as_target INTEGER NOT NULL DEFAULT 0,
                raw_audio_path TEXT NOT NULL,
                ref_8s_path TEXT,
                ref_16s_path TEXT,
                ref_20s_path TEXT,
                ref_25s_path TEXT,
                preview_mp3_path TEXT,
                sha256 TEXT NOT NULL,
                duration_seconds REAL,
                sample_rate INTEGER,
                channels INTEGER,
                source_song_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                archived INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS songs (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                artist TEXT,
                original_audio_path TEXT NOT NULL,
                prepared_audio_path TEXT,
                vocals_path TEXT,
                no_vocals_path TEXT,
                demucs_model TEXT,
                demucs_cache_key TEXT,
                sha256 TEXT NOT NULL,
                duration_seconds REAL,
                sample_rate INTEGER,
                channels INTEGER,
                source_kind TEXT NOT NULL DEFAULT 'full_song',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                archived INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS conversion_jobs (
                id TEXT PRIMARY KEY,
                voice_id TEXT,
                song_id TEXT,
                preset TEXT NOT NULL,
                source_vocal_path TEXT,
                converted_vocal_path TEXT,
                final_wav_path TEXT,
                final_mp3_path TEXT,
                metrics_path TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                finished_at TEXT,
                error_message TEXT
            );
            """
        )
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(songs)")}
        if "source_kind" not in existing:
            conn.execute("ALTER TABLE songs ADD COLUMN source_kind TEXT NOT NULL DEFAULT 'full_song'")


def _voice_from_row(row: sqlite3.Row) -> VoiceProfile:
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


def _song_from_row(row: sqlite3.Row) -> SongRecord:
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


def _existing_voice_by_hash(db_path: Path, file_hash: str) -> VoiceProfile | None:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM voices WHERE sha256 = ? AND archived = 0 ORDER BY created_at LIMIT 1",
            (file_hash,),
        ).fetchone()
    return _voice_from_row(row) if row else None


def _existing_song_by_hash(db_path: Path, file_hash: str) -> SongRecord | None:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM songs WHERE sha256 = ? AND archived = 0 ORDER BY created_at LIMIT 1",
            (file_hash,),
        ).fetchone()
    return _song_from_row(row) if row else None


def _write_metadata(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_preview_mp3(source: Path, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        as_strs(
            [
                "ffmpeg",
                "-y",
                "-i",
                source,
                "-t",
                12,
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "160k",
                output,
            ]
        )
    )
    return output


def _metadata_audio_defaults(path: Path) -> tuple[float | None, int | None, int | None]:
    return probe_duration(path), None, None


def create_voice_profile(
    name: str,
    description: str | None,
    source_type: str,
    rights_status: str,
    allowed_as_target: bool,
    raw_audio_path: Path,
    ref_8s_path: Path | None,
    ref_16s_path: Path | None,
    ref_20s_path: Path | None,
    ref_25s_path: Path | None,
    preview_mp3_path: Path | None,
    sha256: str,
    duration_seconds: float | None = None,
    sample_rate: int | None = None,
    channels: int | None = None,
    source_song_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    voice_id: str | None = None,
) -> VoiceProfile:
    init_library(db_path)
    now = utc_now()
    record = VoiceProfile(
        id=voice_id or make_id("voice"),
        name=name,
        description=description,
        source_type=source_type,
        rights_status=rights_status,
        allowed_as_target=allowed_as_target,
        raw_audio_path=str(raw_audio_path),
        ref_8s_path=str(ref_8s_path) if ref_8s_path else None,
        ref_16s_path=str(ref_16s_path) if ref_16s_path else None,
        ref_20s_path=str(ref_20s_path) if ref_20s_path else None,
        ref_25s_path=str(ref_25s_path) if ref_25s_path else None,
        preview_mp3_path=str(preview_mp3_path) if preview_mp3_path else None,
        sha256=sha256,
        duration_seconds=duration_seconds,
        sample_rate=sample_rate,
        channels=channels,
        source_song_id=source_song_id,
        created_at=now,
        updated_at=now,
    )
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO voices (
                id, name, description, source_type, rights_status, allowed_as_target,
                raw_audio_path, ref_8s_path, ref_16s_path, ref_20s_path, ref_25s_path,
                preview_mp3_path, sha256, duration_seconds, sample_rate, channels,
                source_song_id, created_at, updated_at, archived
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.name,
                record.description,
                record.source_type,
                record.rights_status,
                int(record.allowed_as_target),
                record.raw_audio_path,
                record.ref_8s_path,
                record.ref_16s_path,
                record.ref_20s_path,
                record.ref_25s_path,
                record.preview_mp3_path,
                record.sha256,
                record.duration_seconds,
                record.sample_rate,
                record.channels,
                record.source_song_id,
                record.created_at,
                record.updated_at,
                int(record.archived),
            ),
        )
    return record


def save_voice_to_library(
    input_audio: Path,
    name: str,
    description: str | None = None,
    source_type: str = "upload_voice",
    rights_status: str = "unknown",
    allowed_as_target: bool = False,
    source_song_id: str | None = None,
    library_dir: Path = DEFAULT_LIBRARY_DIR,
    db_path: Path = DEFAULT_DB_PATH,
) -> VoiceProfile:
    init_library(db_path)
    file_hash = sha256_file(input_audio)

    can_target = bool(allowed_as_target and rights_status in {"own_voice", "authorized_voice"})
    if not can_target and rights_status in {"own_voice", "authorized_voice"}:
        rights_status = "unknown"

    voice_id = make_id("voice")
    voice_dir = library_dir / "voices" / voice_id
    voice_dir.mkdir(parents=True, exist_ok=True)
    raw_audio = normalize_audio(input_audio, voice_dir / "raw.wav")
    refs: dict[int, Path] = {}
    for seconds in VOICE_REF_SECONDS:
        refs[seconds] = normalize_audio(
            raw_audio,
            voice_dir / f"ref_{seconds}s.wav",
            duration_seconds=seconds,
        )
    preview = _make_preview_mp3(refs[8], voice_dir / "preview.mp3")
    duration, sample_rate, channels = _metadata_audio_defaults(raw_audio)

    record = create_voice_profile(
        name=name,
        description=description,
        source_type=source_type,
        rights_status=rights_status if can_target else ("source_only" if rights_status == "source_only" else "unknown"),
        allowed_as_target=can_target,
        raw_audio_path=raw_audio,
        ref_8s_path=refs[8],
        ref_16s_path=refs[16],
        ref_20s_path=refs[20],
        ref_25s_path=refs[25],
        preview_mp3_path=preview,
        sha256=file_hash,
        duration_seconds=duration,
        sample_rate=sample_rate,
        channels=channels,
        source_song_id=source_song_id,
        db_path=db_path,
        voice_id=voice_id,
    )
    _write_metadata(voice_dir / "metadata.json", asdict(record))
    return record


def list_voice_profiles(
    include_archived: bool = False,
    only_allowed_targets: bool = False,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[VoiceProfile]:
    init_library(db_path)
    clauses = []
    if not include_archived:
        clauses.append("archived = 0")
    if only_allowed_targets:
        clauses.append("allowed_as_target = 1")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect(db_path) as conn:
        rows = conn.execute(f"SELECT * FROM voices {where} ORDER BY updated_at DESC").fetchall()
    return [_voice_from_row(row) for row in rows]


def get_voice_profile(voice_id: str, db_path: Path = DEFAULT_DB_PATH) -> VoiceProfile:
    init_library(db_path)
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM voices WHERE id = ?", (voice_id,)).fetchone()
    if not row:
        raise KeyError(f"Voice profile not found: {voice_id}")
    return _voice_from_row(row)


def archive_voice_profile(voice_id: str, db_path: Path = DEFAULT_DB_PATH) -> None:
    init_library(db_path)
    with connect(db_path) as conn:
        conn.execute("UPDATE voices SET archived = 1, updated_at = ? WHERE id = ?", (utc_now(), voice_id))


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


def best_voice_reference(profile: VoiceProfile, target_seconds: int) -> Path:
    choices = {
        8: profile.ref_8s_path,
        16: profile.ref_16s_path,
        20: profile.ref_20s_path,
        25: profile.ref_25s_path,
    }
    seconds = min(choices, key=lambda item: abs(item - target_seconds))
    selected = choices[seconds] or profile.raw_audio_path
    return Path(selected)
