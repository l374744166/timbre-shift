"""Lightweight source vocal quality checks before voice conversion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


def analyze_source_vocal_quality(
    vocal_path: Path,
    output_json: Path | None = None,
    segment_seconds: float = 5.0,
) -> dict[str, Any]:
    """Analyze clipping, high-frequency harshness and risky time ranges.

    The scores are intentionally heuristic: they are meant to decide whether to
    suggest a safer repair path, not to be a mastering-grade audio diagnosis.
    """
    audio, sample_rate = sf.read(str(vocal_path), always_2d=False)
    samples = np.asarray(audio, dtype=np.float32)
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    if samples.size == 0:
        raise ValueError(f"音频为空：{vocal_path}")

    segment_size = max(1, int(float(segment_seconds) * sample_rate))
    segments: list[dict[str, Any]] = []
    for index, start in enumerate(range(0, len(samples), segment_size)):
        chunk = samples[start : start + segment_size]
        if chunk.size == 0:
            continue
        metrics = _measure_chunk(chunk, sample_rate)
        risk_level = _risk_level(metrics)
        segments.append(
            {
                "start": round(start / sample_rate, 3),
                "end": round(min(len(samples), start + segment_size) / sample_rate, 3),
                **metrics,
                "risk_level": risk_level,
            }
        )

    overall = _measure_chunk(samples, sample_rate)
    problem_segments = [item for item in segments if item["risk_level"] in {"warning", "bad"}]
    worst_rank = max((_risk_rank(item["risk_level"]) for item in segments), default=0)
    source_quality_score = _quality_score(overall, problem_segments, len(segments))
    has_clipping = bool(overall["clipping_score"] >= 0.01 or overall["peak"] >= 0.98)
    high_freq_risk = bool(overall["high_freq_ratio"] >= 0.22 or any(s["high_freq_ratio"] >= 0.28 for s in segments))
    harshness_risk = bool(overall["harshness_score"] >= 0.55 or any(s["harshness_score"] >= 0.65 for s in segments))
    if worst_rank >= 2 or has_clipping or (high_freq_risk and harshness_risk):
        summary = "高潮段有风险"
    elif worst_rank == 1 or high_freq_risk or harshness_risk or source_quality_score < 80:
        summary = "一般"
    else:
        summary = "良好"
    result: dict[str, Any] = {
        **overall,
        "duration_seconds": round(len(samples) / sample_rate, 3),
        "segment_seconds": float(segment_seconds),
        "segments": segments,
        "problem_segments": problem_segments,
        "source_quality_score": source_quality_score,
        "source_problem_segment_count": len(problem_segments),
        "source_has_clipping": has_clipping,
        "source_high_freq_risk": high_freq_risk,
        "source_harshness_risk": harshness_risk,
        "source_quality_summary": summary,
    }
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _measure_chunk(samples: np.ndarray, sample_rate: int) -> dict[str, float]:
    chunk = np.asarray(samples, dtype=np.float32)
    peak = float(np.max(np.abs(chunk))) if chunk.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(chunk)))) if chunk.size else 0.0
    clipping_score = float(np.mean(np.abs(chunk) >= 0.985)) if chunk.size else 0.0
    zero_crossing_rate = float(np.mean(np.signbit(chunk[1:]) != np.signbit(chunk[:-1]))) if chunk.size > 1 else 0.0
    band_3_6, band_6_10, high_freq_ratio, flatness = _frequency_metrics(chunk, sample_rate)
    harshness_score = _harshness_score(high_freq_ratio, flatness, zero_crossing_rate, clipping_score, peak)
    return {
        "peak": round(peak, 6),
        "rms": round(rms, 6),
        "band_3k_6k_ratio": round(band_3_6, 6),
        "band_6k_10k_ratio": round(band_6_10, 6),
        "high_freq_ratio": round(high_freq_ratio, 6),
        "spectral_flatness": round(flatness, 6),
        "zero_crossing_rate": round(zero_crossing_rate, 6),
        "harshness_score": round(harshness_score, 6),
        "clipping_score": round(clipping_score, 6),
    }


def _frequency_metrics(samples: np.ndarray, sample_rate: int) -> tuple[float, float, float, float]:
    if samples.size < 32:
        return 0.0, 0.0, 0.0, 0.0
    max_samples = min(samples.size, sample_rate * 12)
    stride = max(1, samples.size // max_samples)
    chunk = samples[::stride][:max_samples]
    window = np.hanning(chunk.size).astype(np.float32)
    spectrum = np.abs(np.fft.rfft(chunk * window)) ** 2
    freqs = np.fft.rfftfreq(chunk.size, d=1.0 / sample_rate)
    total = float(np.sum(spectrum) + 1e-12)
    band_3_6 = float(np.sum(spectrum[(freqs >= 3000) & (freqs < 6000)]) / total)
    band_6_10 = float(np.sum(spectrum[(freqs >= 6000) & (freqs < 10000)]) / total)
    high = float(np.sum(spectrum[(freqs >= 3000) & (freqs < min(10000, sample_rate / 2))]) / total)
    positive = spectrum[spectrum > 1e-12]
    flatness = float(np.exp(np.mean(np.log(positive))) / (np.mean(positive) + 1e-12)) if positive.size else 0.0
    return band_3_6, band_6_10, high, flatness


def _harshness_score(high_freq_ratio: float, flatness: float, zcr: float, clipping: float, peak: float) -> float:
    score = 0.0
    score += min(0.45, high_freq_ratio * 1.4)
    score += min(0.25, flatness * 0.7)
    score += min(0.18, zcr * 1.1)
    score += min(0.12, clipping * 8.0)
    if peak >= 0.98:
        score += 0.08
    return float(max(0.0, min(1.0, score)))


def _risk_level(metrics: dict[str, float]) -> str:
    if metrics["clipping_score"] >= 0.02 or metrics["harshness_score"] >= 0.72 or metrics["high_freq_ratio"] >= 0.36:
        return "bad"
    if metrics["peak"] >= 0.98 or metrics["harshness_score"] >= 0.52 or metrics["high_freq_ratio"] >= 0.24:
        return "warning"
    return "ok"


def _risk_rank(level: str) -> int:
    return {"ok": 0, "warning": 1, "bad": 2}.get(level, 0)


def _quality_score(overall: dict[str, float], problems: list[dict[str, Any]], total_segments: int) -> int:
    penalty = overall["harshness_score"] * 45 + overall["clipping_score"] * 500
    if total_segments:
        penalty += (len(problems) / total_segments) * 35
    return int(max(0, min(100, round(100 - penalty))))
