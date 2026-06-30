"""Selectable vocal separation strategies."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .commands import as_strs, require_binary, run_command
from .demucs import SeparationResult, separate_vocals, sha256_file

SEPARATION_MODES = {
    "standard",
    "demucs_high_quality",
    "ai_tolerant",
}

AUDIO_SEPARATOR_DEFAULT_MODEL = "bs_roformer_vocals_revive_v3e_unwa.ckpt"


@dataclass(frozen=True)
class SmartSeparationResult:
    vocals: Path
    backing: Path
    from_cache: bool = False
    engine: str = "demucs"
    mode: str = "standard"
    fallback_used: bool = False
    fallback_reason: str | None = None


def separate_vocals_smart(
    song: Path,
    output_dir: Path,
    mode: str = "standard",
    model: str = "htdemucs",
    cache_dir: Path | None = None,
    overlap: float = 0.10,
    shifts: int = 0,
) -> SmartSeparationResult:
    """Separate vocals using the selected strategy with a safe Demucs fallback."""
    mode = mode if mode in SEPARATION_MODES else "standard"
    if mode == "standard":
        result = separate_vocals(song, output_dir, model=model, cache_dir=cache_dir, overlap=overlap, shifts=shifts)
        return _wrap_demucs(result, mode="standard")

    if mode == "demucs_high_quality":
        result = separate_vocals(
            song,
            output_dir,
            model="htdemucs_ft",
            cache_dir=cache_dir,
            overlap=max(overlap, 0.25),
            shifts=max(shifts, 1),
        )
        return _wrap_demucs(result, mode="demucs_high_quality")

    # The RoFormer/audio-separator direct path can reduce bleed, but on some AI-generated
    # songs it smears consonants badly enough that lyrics become unintelligible after RVC.
    # Until we add a real intelligibility gate or user audition step, keep this mode safe
    # by routing it to high-quality Demucs instead of feeding RoFormer vocals into RVC.
    result = separate_vocals(
        song,
        output_dir,
        model="htdemucs_ft",
        cache_dir=cache_dir,
        overlap=max(overlap, 0.25),
        shifts=max(shifts, 1),
    )
    return SmartSeparationResult(
        vocals=result.vocals,
        backing=result.backing,
        from_cache=result.from_cache,
        engine="demucs_high_quality",
        mode="demucs_high_quality",
        fallback_used=True,
        fallback_reason="AI歌容错分离已保护性改用高质量分离，避免歌词变糊",
    )


def _wrap_demucs(result: SeparationResult, mode: str) -> SmartSeparationResult:
    return SmartSeparationResult(
        vocals=result.vocals,
        backing=result.backing,
        from_cache=result.from_cache,
        engine="demucs",
        mode=mode,
    )


def _separate_with_audio_separator(
    song: Path,
    output_dir: Path,
    cache_dir: Path | None = None,
    model_filename: str = AUDIO_SEPARATOR_DEFAULT_MODEL,
) -> SmartSeparationResult:
    binary = require_binary("audio-separator")
    if not binary:
        raise FileNotFoundError("没有找到 audio-separator，可先用高质量 Demucs 回退")

    cache_key = f"{sha256_file(song)[:24]}-audio-separator-{model_filename}"
    if cache_dir:
        cached_dir = cache_dir / "audio_separator" / cache_key
        cached_vocals = cached_dir / "vocals.wav"
        cached_backing = cached_dir / "no_vocals.wav"
        if cached_vocals.exists() and cached_backing.exists():
            return SmartSeparationResult(
                vocals=cached_vocals,
                backing=cached_backing,
                from_cache=True,
                engine="audio_separator",
                mode="ai_tolerant",
            )

    with tempfile.TemporaryDirectory(prefix="timbre-shift-audio-separator-") as tmp:
        tmp_out = Path(tmp)
        run_command(
            as_strs(
                [
                    binary,
                    song,
                    "--model_filename",
                    model_filename,
                    "--output_dir",
                    tmp_out,
                    "--output_format",
                    "WAV",
                ]
            )
        )
        vocals = _find_stem(tmp_out, kind="vocals")
        backing = _find_stem(tmp_out, kind="backing")
        if not vocals or not backing:
            found = ", ".join(path.name for path in tmp_out.glob("*.wav"))
            raise FileNotFoundError(f"audio-separator 没有产出完整人声/伴奏：{found}")

        target_dir = cache_dir / "audio_separator" / cache_key if cache_dir else output_dir / "audio_separator" / song.stem
        target_dir.mkdir(parents=True, exist_ok=True)
        target_vocals = target_dir / "vocals.wav"
        target_backing = target_dir / "no_vocals.wav"
        shutil.copy2(vocals, target_vocals)
        shutil.copy2(backing, target_backing)
        return SmartSeparationResult(
            vocals=target_vocals,
            backing=target_backing,
            from_cache=False,
            engine="audio_separator",
            mode="ai_tolerant",
        )


def _find_stem(output_dir: Path, kind: str) -> Path | None:
    candidates = sorted(output_dir.rglob("*.wav"))
    if kind == "vocals":
        keywords = ["vocal", "voice", "sing"]
        negative = ["no_vocal", "novocal", "instrumental", "accompaniment", "karaoke", "inst"]
    else:
        keywords = ["instrumental", "accompaniment", "karaoke", "no_vocal", "novocal", "inst", "other"]
        negative = []
    for path in candidates:
        name = path.stem.lower().replace(" ", "_").replace("-", "_")
        if any(word in name for word in keywords) and not any(word in name for word in negative):
            return path
    return candidates[0] if kind == "vocals" and len(candidates) == 1 else None
