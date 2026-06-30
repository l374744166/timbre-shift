"""Blend a repaired vocal only into risky time ranges."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


def blend_problem_segments(
    base_vocal: Path,
    repair_vocal: Path,
    output: Path,
    problem_segments: list[dict[str, Any]],
    wet: float = 0.55,
    fade_seconds: float = 0.08,
) -> Path:
    """Blend ``repair_vocal`` into ``base_vocal`` only around risky segments.

    This keeps clean details from the normal render and uses the heavy rescue
    render only where the source-quality checker found obvious harshness.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    base, sample_rate = _read_mono(base_vocal)
    repair, repair_rate = _read_mono(repair_vocal)
    if repair_rate != sample_rate:
        raise ValueError(f"采样率不一致：{sample_rate} != {repair_rate}")

    if repair.size < base.size:
        repair = np.pad(repair, (0, base.size - repair.size))
    repair = repair[: base.size]

    mask = _segment_mask(base.size, sample_rate, problem_segments, wet=wet, fade_seconds=fade_seconds)
    if not np.any(mask):
        sf.write(str(output), base, sample_rate)
        return output

    mixed = base * (1.0 - mask) + repair * mask
    mixed = np.clip(mixed, -0.98, 0.98).astype(np.float32)
    sf.write(str(output), mixed, sample_rate)
    return output


def _read_mono(path: Path) -> tuple[np.ndarray, int]:
    audio, sample_rate = sf.read(str(path), always_2d=False)
    data = np.asarray(audio, dtype=np.float32)
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data, int(sample_rate)


def _segment_mask(
    sample_count: int,
    sample_rate: int,
    problem_segments: list[dict[str, Any]],
    wet: float,
    fade_seconds: float,
) -> np.ndarray:
    mask = np.zeros(sample_count, dtype=np.float32)
    wet = float(max(0.0, min(1.0, wet)))
    fade_samples = max(1, int(float(fade_seconds) * sample_rate))
    for segment in problem_segments:
        try:
            start_seconds = float(segment.get("start", 0.0))
            end_seconds = float(segment.get("end", 0.0))
        except (TypeError, ValueError):
            continue
        start = max(0, min(sample_count, int(round(start_seconds * sample_rate))))
        end = max(0, min(sample_count, int(round(end_seconds * sample_rate))))
        if end <= start:
            continue
        segment_mask = np.full(end - start, wet, dtype=np.float32)
        fade = min(fade_samples, max(1, segment_mask.size // 2))
        if fade > 1:
            ramp_in = np.linspace(0.0, wet, fade, dtype=np.float32)
            ramp_out = np.linspace(wet, 0.0, fade, dtype=np.float32)
            segment_mask[:fade] = np.minimum(segment_mask[:fade], ramp_in)
            segment_mask[-fade:] = np.minimum(segment_mask[-fade:], ramp_out)
        mask[start:end] = np.maximum(mask[start:end], segment_mask)
    return mask
