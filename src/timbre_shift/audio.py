"""Audio preparation and mixing commands."""

from __future__ import annotations

from pathlib import Path

from .commands import as_strs, run_command


def normalize_audio(
    source: Path,
    target: Path,
    sample_rate: int = 44100,
    duration_seconds: int | None = None,
) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        source,
        "-ac",
        1,
        "-ar",
        sample_rate,
        "-vn",
    ]
    if duration_seconds:
        command.extend(["-t", duration_seconds])
    command.append(target)
    run_command(
        as_strs(command)
    )
    return target


def mix_audio(
    converted_vocal: Path,
    backing_track: Path,
    output: Path,
    vocal_volume: float = 1.0,
    backing_volume: float = 0.9,
    limiter: float = 0.95,
) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    filter_complex = (
        f"[0:a]volume={vocal_volume},highpass=f=80,"
        "acompressor=threshold=-18dB:ratio=2.5:attack=10:release=80[v];"
        f"[1:a]volume={backing_volume}[b];"
        f"[v][b]amix=inputs=2:duration=longest:normalize=0,"
        f"alimiter=limit={limiter}[out]"
    )
    run_command(
        as_strs(
            [
                "ffmpeg",
                "-y",
                "-i",
                converted_vocal,
                "-i",
                backing_track,
                "-filter_complex",
                filter_complex,
                "-map",
                "[out]",
                output,
            ]
        )
    )
    return output
