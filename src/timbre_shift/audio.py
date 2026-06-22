"""Audio preparation and mixing commands."""

from __future__ import annotations

from pathlib import Path

from .commands import as_strs, run_command


def probe_duration(source: Path) -> float | None:
    import subprocess

    result = subprocess.run(
        as_strs(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                source,
            ]
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def middle_start(source: Path, duration_seconds: int | None) -> float | None:
    if not duration_seconds:
        return None
    duration = probe_duration(source)
    if duration is None or duration <= duration_seconds:
        return None
    return max(0.0, (duration - duration_seconds) / 2)


def normalize_audio(
    source: Path,
    target: Path,
    sample_rate: int = 44100,
    duration_seconds: int | None = None,
    start_seconds: float | None = None,
) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
    ]
    if start_seconds is not None and start_seconds > 0:
        command.extend(["-ss", f"{start_seconds:.3f}"])
    command.extend(
        [
        "-i",
        source,
        "-ac",
        1,
        "-ar",
        sample_rate,
        "-vn",
        ]
    )
    if duration_seconds:
        command.extend(["-t", duration_seconds])
    command.append(target)
    run_command(
        as_strs(command)
    )
    return target


def split_audio_fixed(source: Path, output_dir: Path, chunk_seconds: int) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = output_dir / "chunk_%04d.wav"
    run_command(
        as_strs(
            [
                "ffmpeg",
                "-y",
                "-i",
                source,
                "-f",
                "segment",
                "-segment_time",
                chunk_seconds,
                "-reset_timestamps",
                "1",
                "-ac",
                1,
                "-ar",
                44100,
                pattern,
            ]
        )
    )
    return sorted(output_dir.glob("chunk_*.wav"))


def concat_audio_files(sources: list[Path], output: Path) -> Path:
    if not sources:
        raise ValueError("No audio chunks to concatenate")
    output.parent.mkdir(parents=True, exist_ok=True)
    list_file = output.parent / f"{output.stem}_concat.txt"
    lines = []
    for source in sources:
        escaped = str(source.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run_command(
        as_strs(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_file,
                "-c",
                "copy",
                output,
            ]
        )
    )
    return output


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


def limit_audio_peak(source: Path, output: Path, peak_limit: float = 0.92) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    filters = ",".join(
        [
            f"alimiter=limit={peak_limit}",
            f"loudnorm=I=-16:TP=-1.0:LRA=11",
            f"alimiter=limit={peak_limit}",
        ]
    )
    run_command(
        as_strs(
            [
                "ffmpeg",
                "-y",
                "-i",
                source,
                "-af",
                filters,
                "-ac",
                "1",
                "-ar",
                "44100",
                output,
            ]
        )
    )
    return output


def polish_vocal(
    source: Path,
    output: Path,
    sample_rate: int = 44100,
) -> Path:
    """Post-process the converted vocal so it sits better in a song mix."""
    output.parent.mkdir(parents=True, exist_ok=True)
    filters = ",".join(
        [
            "highpass=f=70",
            "lowpass=f=15500",
            "equalizer=f=250:t=q:w=1.1:g=-1.8",
            "equalizer=f=3200:t=q:w=1.0:g=1.4",
            "equalizer=f=8500:t=q:w=1.2:g=1.0",
            "deesser=i=0.35:m=0.55:f=0.45",
            "acompressor=threshold=-20dB:ratio=2.2:attack=8:release=90:makeup=1.8",
            "alimiter=limit=0.92",
            "loudnorm=I=-18:TP=-1.5:LRA=11",
        ]
    )
    run_command(
        as_strs(
            [
                "ffmpeg",
                "-y",
                "-i",
                source,
                "-af",
                filters,
                "-ac",
                1,
                "-ar",
                sample_rate,
                output,
            ]
        )
    )
    return output


def export_mp3(source: Path, output: Path, bitrate: str = "192k") -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        as_strs(
            [
                "ffmpeg",
                "-y",
                "-i",
                source,
                "-codec:a",
                "libmp3lame",
                "-b:a",
                bitrate,
                output,
            ]
        )
    )
    return output
