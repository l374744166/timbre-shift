"""Demucs vocal separation wrapper."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .commands import as_strs, run_command


@dataclass(frozen=True)
class SeparationResult:
    vocals: Path
    backing: Path
    from_cache: bool = False


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def separate_vocals(
    song: Path,
    output_dir: Path,
    model: str = "htdemucs",
    cache_dir: Path | None = None,
    overlap: float = 0.10,
    shifts: int = 0,
) -> SeparationResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_key = f"{sha256_file(song)[:24]}-{model}-ov{overlap}-sh{shifts}"
    if cache_dir:
        cached_dir = cache_dir / "demucs" / cache_key
        cached_vocals = cached_dir / "vocals.wav"
        cached_backing = cached_dir / "no_vocals.wav"
        if cached_vocals.exists() and cached_backing.exists():
            return SeparationResult(vocals=cached_vocals, backing=cached_backing, from_cache=True)

    with tempfile.TemporaryDirectory(prefix="timbre-shift-demucs-") as tmp:
        tmp_out = Path(tmp)
        run_command(
            as_strs(
                [
                    "demucs",
                    "--two-stems",
                    "vocals",
                    "-n",
                    model,
                    "--overlap",
                    overlap,
                    "--shifts",
                    shifts,
                    "-o",
                    tmp_out,
                    song,
                ]
            )
        )
        stem_dir = tmp_out / model / song.stem
        vocals = stem_dir / "vocals.wav"
        backing = stem_dir / "no_vocals.wav"
        if not vocals.exists() or not backing.exists():
            raise FileNotFoundError(f"Demucs output not found under {stem_dir}")

        if cache_dir:
            cached_dir = cache_dir / "demucs" / cache_key
            cached_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(vocals, cached_dir / "vocals.wav")
            shutil.copy2(backing, cached_dir / "no_vocals.wav")
            return SeparationResult(
                vocals=cached_dir / "vocals.wav",
                backing=cached_dir / "no_vocals.wav",
            )

        final_dir = output_dir / model / song.stem
        final_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(vocals, final_dir / "vocals.wav")
        shutil.copy2(backing, final_dir / "no_vocals.wav")
        return SeparationResult(vocals=final_dir / "vocals.wav", backing=final_dir / "no_vocals.wav")
