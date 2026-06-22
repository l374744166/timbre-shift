"""SQLite connection and schema management for the asset library."""

from __future__ import annotations

import sqlite3
from pathlib import Path


DEFAULT_LIBRARY_DIR = Path("data/library")
DEFAULT_DB_PATH = DEFAULT_LIBRARY_DIR / "timbre_shift.db"
VOICE_REF_SECONDS = (8, 16, 20, 25)

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
            CREATE TABLE IF NOT EXISTS voice_samples (
                id TEXT PRIMARY KEY,
                voice_id TEXT NOT NULL,
                name TEXT,
                raw_audio_path TEXT NOT NULL,
                clean_audio_path TEXT,
                source_type TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                duration_seconds REAL,
                sample_rate INTEGER,
                channels INTEGER,
                quality_score REAL,
                noise_score REAL,
                notes TEXT,
                created_at TEXT NOT NULL,
                archived INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS voice_models (
                id TEXT PRIMARY KEY,
                voice_id TEXT NOT NULL,
                engine_id TEXT NOT NULL,
                model_name TEXT NOT NULL,
                model_path TEXT NOT NULL,
                index_path TEXT,
                config_path TEXT,
                dataset_path TEXT,
                training_seconds REAL,
                dataset_seconds REAL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata_json TEXT,
                archived INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(songs)")}
        if "source_kind" not in existing:
            conn.execute("ALTER TABLE songs ADD COLUMN source_kind TEXT NOT NULL DEFAULT 'full_song'")

