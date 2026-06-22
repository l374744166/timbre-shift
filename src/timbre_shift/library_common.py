"""Shared helpers for the local asset library."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .audio import probe_duration
from .commands import as_strs, run_command
from .library_db import connect
from .library_models import SongRecord, VoiceProfile
from .library_rows import song_from_row as _song_from_row, voice_from_row as _voice_from_row


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


def _concat_audio_files(sources: list[Path], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    if not sources:
        raise ValueError("No audio files to combine")
    if len(sources) == 1:
        shutil.copy2(sources[0], output)
        return output
    command = ["ffmpeg", "-y"]
    for source in sources:
        command.extend(["-i", source])
    labels = "".join(f"[{index}:a]" for index in range(len(sources)))
    command.extend(
        [
            "-filter_complex",
            f"{labels}concat=n={len(sources)}:v=0:a=1[out]",
            "-map",
            "[out]",
            output,
        ]
    )
    run_command(as_strs(command))
    return output


def _score_quality(report: dict[str, object]) -> tuple[float, float]:
    issues = [item for item in report.get("issues", []) if isinstance(item, dict)]
    weights = {"high": 0.25, "medium": 0.14, "low": 0.07}
    penalty = sum(weights.get(str(issue.get("confidence")), 0.05) for issue in issues)
    quality_score = max(0.0, min(1.0, 1.0 - penalty))
    noise_score = min(1.0, penalty)
    return quality_score, noise_score
