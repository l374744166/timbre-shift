"""Voice profile records and reference audio management."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .audio import normalize_audio
from .library_common import _make_preview_mp3, _metadata_audio_defaults, _write_metadata, make_id, sha256_file, utc_now
from .library_db import DEFAULT_DB_PATH, DEFAULT_LIBRARY_DIR, VOICE_REF_SECONDS, connect, init_library
from .library_models import VoiceProfile
from .library_rows import voice_from_row as _voice_from_row


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
    clean_audio: Path | None = None,
    description: str | None = None,
    source_type: str = "upload_voice",
    rights_status: str = "unknown",
    allowed_as_target: bool = False,
    source_song_id: str | None = None,
    library_dir: Path = DEFAULT_LIBRARY_DIR,
    db_path: Path = DEFAULT_DB_PATH,
) -> VoiceProfile:
    from .library_samples import add_voice_sample_to_profile

    init_library(db_path)
    file_hash = sha256_file(input_audio)

    can_target = bool(allowed_as_target and rights_status in {"own_voice", "authorized_voice"})
    if not can_target and rights_status in {"own_voice", "authorized_voice"}:
        rights_status = "unknown"

    voice_id = make_id("voice")
    voice_dir = library_dir / "voices" / voice_id
    voice_dir.mkdir(parents=True, exist_ok=True)
    reference_source = clean_audio or input_audio
    raw_audio = normalize_audio(reference_source, voice_dir / "raw.wav")
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
    add_voice_sample_to_profile(
        voice_id=record.id,
        input_audio=input_audio,
        clean_audio=raw_audio,
        name=name,
        source_type=source_type,
        library_dir=library_dir,
        db_path=db_path,
        require_allowed_target=False,
    )
    return record


def create_empty_voice_profile(
    name: str,
    description: str | None = None,
    source_type: str = "rvc_training_library",
    rights_status: str = "own_voice",
    allowed_as_target: bool = True,
    library_dir: Path = DEFAULT_LIBRARY_DIR,
    db_path: Path = DEFAULT_DB_PATH,
) -> VoiceProfile:
    """Create an empty target voice library for later training samples."""
    init_library(db_path)
    voice_id = make_id("voice")
    voice_dir = library_dir / "voices" / voice_id
    voice_dir.mkdir(parents=True, exist_ok=True)
    raw_audio = voice_dir / "raw.wav"
    record = create_voice_profile(
        name=name.strip() or "未命名音色库",
        description=description,
        source_type=source_type,
        rights_status=rights_status,
        allowed_as_target=allowed_as_target,
        raw_audio_path=raw_audio,
        ref_8s_path=None,
        ref_16s_path=None,
        ref_20s_path=None,
        ref_25s_path=None,
        preview_mp3_path=None,
        sha256=f"empty:{voice_id}",
        duration_seconds=0.0,
        sample_rate=None,
        channels=None,
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
