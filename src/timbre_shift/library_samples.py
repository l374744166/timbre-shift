"""Voice training/reference sample management."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .audio import normalize_audio
from .diagnostics import AnalyzerContext, analyze_generation
from .library_common import _concat_audio_files, _make_preview_mp3, _metadata_audio_defaults, _score_quality, _write_metadata, make_id, sha256_file, utc_now
from .library_db import DEFAULT_DB_PATH, DEFAULT_LIBRARY_DIR, VOICE_REF_SECONDS, connect, init_library
from .library_models import VoiceProfile, VoiceSample
from .library_rows import voice_sample_from_row as _voice_sample_from_row
from .library_voices import get_voice_profile


def create_voice_sample_record(
    voice_id: str,
    name: str | None,
    raw_audio_path: Path,
    clean_audio_path: Path | None,
    source_type: str,
    sha256: str,
    duration_seconds: float | None = None,
    sample_rate: int | None = None,
    channels: int | None = None,
    quality_score: float | None = None,
    noise_score: float | None = None,
    notes: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    sample_id: str | None = None,
) -> VoiceSample:
    init_library(db_path)
    now = utc_now()
    record = VoiceSample(
        id=sample_id or make_id("sample"),
        voice_id=voice_id,
        name=name,
        raw_audio_path=str(raw_audio_path),
        clean_audio_path=str(clean_audio_path) if clean_audio_path else None,
        source_type=source_type,
        sha256=sha256,
        duration_seconds=duration_seconds,
        sample_rate=sample_rate,
        channels=channels,
        quality_score=quality_score,
        noise_score=noise_score,
        notes=notes,
        created_at=now,
    )
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO voice_samples (
                id, voice_id, name, raw_audio_path, clean_audio_path, source_type,
                sha256, duration_seconds, sample_rate, channels, quality_score,
                noise_score, notes, created_at, archived
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.voice_id,
                record.name,
                record.raw_audio_path,
                record.clean_audio_path,
                record.source_type,
                record.sha256,
                record.duration_seconds,
                record.sample_rate,
                record.channels,
                record.quality_score,
                record.noise_score,
                record.notes,
                record.created_at,
                int(record.archived),
            ),
        )
    return record


def list_voice_samples(
    voice_id: str,
    include_archived: bool = False,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[VoiceSample]:
    init_library(db_path)
    where = "WHERE voice_id = ?"
    if not include_archived:
        where += " AND archived = 0"
    with connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM voice_samples {where} ORDER BY created_at ASC",
            (voice_id,),
        ).fetchall()
    return [_voice_sample_from_row(row) for row in rows]


def get_voice_sample(sample_id: str, db_path: Path = DEFAULT_DB_PATH) -> VoiceSample:
    init_library(db_path)
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM voice_samples WHERE id = ?", (sample_id,)).fetchone()
    if not row:
        raise KeyError(f"Voice sample not found: {sample_id}")
    return _voice_sample_from_row(row)


def archive_voice_sample(sample_id: str, db_path: Path = DEFAULT_DB_PATH) -> None:
    init_library(db_path)
    with connect(db_path) as conn:
        conn.execute("UPDATE voice_samples SET archived = 1 WHERE id = ?", (sample_id,))


def refresh_voice_profile_references(
    voice_id: str,
    library_dir: Path = DEFAULT_LIBRARY_DIR,
    db_path: Path = DEFAULT_DB_PATH,
) -> VoiceProfile:
    profile = get_voice_profile(voice_id, db_path=db_path)
    voice_dir = library_dir / "voices" / voice_id
    samples = list_voice_samples(voice_id, db_path=db_path)
    clean_sources = [
        Path(sample.clean_audio_path or sample.raw_audio_path)
        for sample in samples
        if Path(sample.clean_audio_path or sample.raw_audio_path).exists()
    ]
    if not clean_sources:
        return profile

    raw_audio = _concat_audio_files(clean_sources, voice_dir / "raw.wav")
    refs: dict[int, Path] = {}
    for seconds in VOICE_REF_SECONDS:
        refs[seconds] = normalize_audio(
            raw_audio,
            voice_dir / f"ref_{seconds}s.wav",
            duration_seconds=seconds,
        )
    preview = _make_preview_mp3(refs[8], voice_dir / "preview.mp3")
    duration, sample_rate, channels = _metadata_audio_defaults(raw_audio)
    with connect(db_path) as conn:
        conn.execute(
            """
            UPDATE voices
            SET raw_audio_path = ?, ref_8s_path = ?, ref_16s_path = ?,
                ref_20s_path = ?, ref_25s_path = ?, preview_mp3_path = ?,
                duration_seconds = ?, sample_rate = ?, channels = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                str(raw_audio),
                str(refs[8]),
                str(refs[16]),
                str(refs[20]),
                str(refs[25]),
                str(preview),
                duration,
                sample_rate,
                channels,
                utc_now(),
                voice_id,
            ),
        )
    updated = get_voice_profile(voice_id, db_path=db_path)
    _write_metadata(voice_dir / "metadata.json", asdict(updated))
    return updated


def add_voice_sample_to_profile(
    voice_id: str,
    input_audio: Path,
    clean_audio: Path | None = None,
    name: str | None = None,
    source_type: str = "upload_voice",
    library_dir: Path = DEFAULT_LIBRARY_DIR,
    db_path: Path = DEFAULT_DB_PATH,
    require_allowed_target: bool = True,
) -> VoiceSample:
    profile = get_voice_profile(voice_id, db_path=db_path)
    if require_allowed_target and not profile.allowed_as_target:
        raise PermissionError("这个音色没有授权为目标音色，不能继续添加素材")
    file_hash = sha256_file(input_audio)
    with connect(db_path) as conn:
        existing = conn.execute(
            """
            SELECT * FROM voice_samples
            WHERE voice_id = ? AND sha256 = ? AND archived = 0
            ORDER BY created_at LIMIT 1
            """,
            (voice_id, file_hash),
        ).fetchone()
    if existing:
        return _voice_sample_from_row(existing)

    sample_id = make_id("sample")
    sample_dir = library_dir / "voices" / voice_id / "samples" / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)
    raw_audio = normalize_audio(input_audio, sample_dir / "raw.wav")
    clean_source = clean_audio or input_audio
    clean_path = normalize_audio(clean_source, sample_dir / "clean.wav")
    report = analyze_generation(AnalyzerContext(source_vocal=clean_path))
    quality_score, noise_score = _score_quality(report)
    duration, sample_rate, channels = _metadata_audio_defaults(clean_path)
    record = create_voice_sample_record(
        voice_id=voice_id,
        name=name or input_audio.stem,
        raw_audio_path=raw_audio,
        clean_audio_path=clean_path,
        source_type=source_type,
        sha256=file_hash,
        duration_seconds=duration,
        sample_rate=sample_rate,
        channels=channels,
        quality_score=quality_score,
        noise_score=noise_score,
        notes=json.dumps(report, ensure_ascii=False),
        db_path=db_path,
        sample_id=sample_id,
    )
    _write_metadata(sample_dir / "metadata.json", asdict(record))
    refresh_voice_profile_references(voice_id, library_dir=library_dir, db_path=db_path)
    return record


def add_voice_sample(
    voice_id: str,
    input_audio: Path,
    name: str | None,
    source_type: str,
    notes: str | None = None,
    library_dir: Path = DEFAULT_LIBRARY_DIR,
    db_path: Path = DEFAULT_DB_PATH,
) -> VoiceSample:
    sample = add_voice_sample_to_profile(
        voice_id=voice_id,
        input_audio=input_audio,
        name=name,
        source_type=source_type,
        library_dir=library_dir,
        db_path=db_path,
        require_allowed_target=True,
    )
    if notes:
        with connect(db_path) as conn:
            conn.execute("UPDATE voice_samples SET notes = ? WHERE id = ?", (notes, sample.id))
        return get_voice_sample(sample.id, db_path=db_path)
    return sample
