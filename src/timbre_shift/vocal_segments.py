"""Vocal activity compaction for faster conversion."""

from __future__ import annotations

import re
import subprocess
import json
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path

from .audio import probe_duration
from .commands import as_strs, run_command


@dataclass(frozen=True)
class VocalSegment:
    original_start: float
    original_end: float
    compact_start: float = 0.0

    @property
    def duration(self) -> float:
        return max(0.0, self.original_end - self.original_start)

    @property
    def compact_end(self) -> float:
        return self.compact_start + self.duration


@dataclass(frozen=True)
class CompactVocalResult:
    audio: Path
    segments: list[VocalSegment]
    total_duration: float

    @property
    def active_duration(self) -> float:
        return sum(segment.duration for segment in self.segments)


SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9.]+)")
SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9.]+)")


def detect_vocal_segments(
    vocals: Path,
    noise_db: str = "-45dB",
    min_silence_duration: float = 0.35,
    padding: float = 0.35,
    merge_gap: float = 0.80,
    min_segment_duration: float = 1.0,
) -> tuple[list[VocalSegment], float]:
    """Detect non-silent regions in a vocal stem using ffmpeg silencedetect."""
    total_duration = probe_duration(vocals) or 0.0
    if total_duration <= 0:
        return [], 0.0

    command = as_strs(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            vocals,
            "-af",
            f"silencedetect=n={noise_db}:d={min_silence_duration}",
            "-f",
            "null",
            "-",
        ]
    )
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    silences: list[tuple[float, float]] = []
    current_start: float | None = None
    for line in result.stderr.splitlines():
        start_match = SILENCE_START_RE.search(line)
        if start_match:
            current_start = float(start_match.group(1))
            continue
        end_match = SILENCE_END_RE.search(line)
        if end_match and current_start is not None:
            silences.append((current_start, float(end_match.group(1))))
            current_start = None
    if current_start is not None:
        silences.append((current_start, total_duration))

    raw_segments: list[tuple[float, float]] = []
    cursor = 0.0
    for silence_start, silence_end in silences:
        if silence_start > cursor:
            raw_segments.append((cursor, silence_start))
        cursor = max(cursor, silence_end)
    if cursor < total_duration:
        raw_segments.append((cursor, total_duration))
    if not raw_segments:
        return [], total_duration

    padded = [
        (max(0.0, start - padding), min(total_duration, end + padding))
        for start, end in raw_segments
        if end - start >= min_segment_duration
    ]
    if not padded:
        return [], total_duration

    merged: list[tuple[float, float]] = []
    for start, end in padded:
        if not merged or start - merged[-1][1] > merge_gap:
            merged.append((start, end))
        else:
            last_start, last_end = merged[-1]
            merged[-1] = (last_start, max(last_end, end))

    compact_cursor = 0.0
    segments: list[VocalSegment] = []
    for start, end in merged:
        segment = VocalSegment(start, end, compact_cursor)
        segments.append(segment)
        compact_cursor += segment.duration
    return segments, total_duration


def compact_vocals(vocals: Path, output: Path, segments: list[VocalSegment]) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    if not segments:
        raise ValueError("没有检测到可转换的人声片段")

    chains = []
    labels = []
    for index, segment in enumerate(segments):
        label = f"s{index}"
        chains.append(
            f"[0:a]atrim=start={segment.original_start:.3f}:end={segment.original_end:.3f},"
            f"asetpts=PTS-STARTPTS[{label}]"
        )
        labels.append(f"[{label}]")
    filter_complex = ";".join(chains + [f"{''.join(labels)}concat=n={len(labels)}:v=0:a=1[out]"])
    run_command(
        as_strs(
            [
                "ffmpeg",
                "-y",
                "-i",
                vocals,
                "-filter_complex",
                filter_complex,
                "-map",
                "[out]",
                output,
            ]
        )
    )
    return output


def restore_compact_vocals(
    converted_compact: Path,
    output: Path,
    segments: list[VocalSegment],
    total_duration: float,
    sample_rate: int = 44100,
    fade_seconds: float = 0.020,
) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    if not segments:
        raise ValueError("没有可还原的人声片段")

    chains = []
    labels = ["[0:a]"]
    for index, segment in enumerate(segments):
        label = f"p{index}"
        delay_ms = int(round(segment.original_start * 1000))
        fade_out_start = max(0.0, segment.duration - fade_seconds)
        chains.append(
            f"[1:a]atrim=start={segment.compact_start:.3f}:end={segment.compact_end:.3f},"
            f"asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={fade_seconds:.3f},"
            f"afade=t=out:st={fade_out_start:.3f}:d={fade_seconds:.3f},"
            f"adelay={delay_ms}|{delay_ms}[{label}]"
        )
        labels.append(f"[{label}]")
    filter_complex = ";".join(
        chains + [f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:normalize=0[out]"]
    )
    run_command(
        as_strs(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-t",
                f"{total_duration:.3f}",
                "-i",
                f"anullsrc=r={sample_rate}:cl=mono",
                "-i",
                converted_compact,
                "-filter_complex",
                filter_complex,
                "-map",
                "[out]",
                "-t",
                f"{total_duration:.3f}",
                output,
            ]
        )
    )
    return output


def compact_for_conversion(vocals: Path, output: Path) -> CompactVocalResult:
    segments, total_duration = detect_vocal_segments(vocals)
    if not segments:
        raise ValueError("没有检测到有效人声片段，无法继续转换")
    segments_path = output.with_name("segments.json")
    segments_path.parent.mkdir(parents=True, exist_ok=True)
    active_duration = sum(segment.duration for segment in segments)
    segments_path.write_text(
        json.dumps(
            {
                "total_duration": total_duration,
                "active_vocal_seconds": active_duration,
                "active_ratio": active_duration / total_duration if total_duration else None,
                "segments": [asdict(segment) for segment in segments],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    compact = compact_vocals(vocals, output, segments)
    return CompactVocalResult(audio=compact, segments=segments, total_duration=total_duration)


def map_compact_problem_segments(
    problem_segments: list[dict],
    compact_segments: list[VocalSegment],
) -> list[dict]:
    """Map problem segments measured on compact audio back to original timeline."""
    mapped: list[dict] = []
    for problem in problem_segments:
        try:
            problem_start = float(problem.get("start", 0.0))
            problem_end = float(problem.get("end", 0.0))
        except (TypeError, ValueError):
            continue
        if problem_end <= problem_start:
            continue
        for segment in compact_segments:
            overlap_start = max(problem_start, segment.compact_start)
            overlap_end = min(problem_end, segment.compact_end)
            if overlap_end <= overlap_start:
                continue
            mapped_problem = dict(problem)
            mapped_problem["start"] = round(segment.original_start + (overlap_start - segment.compact_start), 3)
            mapped_problem["end"] = round(segment.original_start + (overlap_end - segment.compact_start), 3)
            mapped.append(mapped_problem)
    return mapped
