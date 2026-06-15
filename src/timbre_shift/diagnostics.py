"""Pluggable audio diagnostics for generated voice conversions."""

from __future__ import annotations

import math
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class DiagnosticTolerances:
    clipping_ratio_warn: float = 0.001
    silence_ratio_warn: float = 0.55
    high_frequency_ratio_warn: float = 0.24
    low_frequency_ratio_warn: float = 0.34
    loudness_min_dbfs: float = -28.0
    loudness_max_dbfs: float = -10.0
    peak_warn: float = 0.98


@dataclass(frozen=True)
class AnalyzerContext:
    source_vocal: Path | None = None
    converted_vocal: Path | None = None
    polished_vocal: Path | None = None
    final_mix: Path | None = None
    backing_track: Path | None = None
    active_ratio: float | None = None


class AudioAnalyzer(Protocol):
    name: str

    def analyze(self, context: AnalyzerContext, tolerances: DiagnosticTolerances) -> dict[str, object]:
        """Return a JSON-serializable diagnostic payload."""


def analyze_generation(
    context: AnalyzerContext,
    tolerances: DiagnosticTolerances | None = None,
    analyzers: list[AudioAnalyzer] | None = None,
) -> dict[str, object]:
    active_tolerances = tolerances or DiagnosticTolerances()
    active_analyzers = analyzers or [RuleBasedAudioAnalyzer()]
    results: list[dict[str, object]] = []
    suggestions: list[str] = []
    issues: list[dict[str, object]] = []

    for analyzer in active_analyzers:
        try:
            result = analyzer.analyze(context, active_tolerances)
        except Exception as exc:
            result = {
                "analyzer": analyzer.name,
                "status": "error",
                "error": str(exc),
                "issues": [],
                "suggestions": [],
            }
        results.append(result)
        suggestions.extend(str(item) for item in result.get("suggestions", []))
        issues.extend(dict(item) for item in result.get("issues", []) if isinstance(item, dict))

    most_likely = _most_likely_issue(issues)
    return {
        "version": 1,
        "status": "completed",
        "analyzer_chain": [analyzer.name for analyzer in active_analyzers],
        "most_likely_issue": most_likely["message"] if most_likely else "未发现明显异常",
        "confidence": most_likely["confidence"] if most_likely else "low",
        "issues": issues,
        "suggestions": _dedupe(suggestions),
        "results": results,
        "tolerances": active_tolerances.__dict__,
    }


class RuleBasedAudioAnalyzer:
    name = "rules_v1"

    def analyze(self, context: AnalyzerContext, tolerances: DiagnosticTolerances) -> dict[str, object]:
        tracks = {
            "source_vocal": _audio_stats(context.source_vocal),
            "converted_vocal": _audio_stats(context.converted_vocal),
            "polished_vocal": _audio_stats(context.polished_vocal),
            "final_mix": _audio_stats(context.final_mix),
            "backing_track": _audio_stats(context.backing_track),
        }
        issues: list[dict[str, object]] = []
        suggestions: list[str] = []

        source = tracks["source_vocal"]
        if source and source["ok"]:
            if source["silence_ratio"] > tolerances.silence_ratio_warn:
                issues.append(_issue("source_vocal_sparse", "原歌分离人声有效内容偏少", "medium", source["silence_ratio"]))
                suggestions.append("使用离线最高质量或重新上传更清晰的歌曲源")
            if source["low_frequency_ratio"] > tolerances.low_frequency_ratio_warn:
                issues.append(_issue("source_vocal_low_residue", "分离人声低频残留偏多，可能有伴奏/鼓点残留", "medium", source["low_frequency_ratio"]))
                suggestions.append("优先使用高质量分离，并开启更强低噪优化")

        converted = tracks["converted_vocal"]
        if converted and converted["ok"]:
            if converted["high_frequency_ratio"] > tolerances.high_frequency_ratio_warn:
                issues.append(_issue("converted_harshness", "换声后高频毛刺偏高", "medium", converted["high_frequency_ratio"]))
                suggestions.append("使用低噪/温暖后处理，或换更干净的音色参考")
            if converted["clipping_ratio"] > tolerances.clipping_ratio_warn or converted["peak"] > tolerances.peak_warn:
                issues.append(_issue("converted_clipping", "换声后可能有爆音或削波", "high", converted["clipping_ratio"]))
                suggestions.append("降低换声人声音量并加强限幅")

        polished = tracks["polished_vocal"]
        if polished and polished["ok"]:
            if polished["rms_dbfs"] < tolerances.loudness_min_dbfs or polished["rms_dbfs"] > tolerances.loudness_max_dbfs:
                issues.append(_issue("polished_loudness", "优化后人声响度不在推荐范围", "low", polished["rms_dbfs"]))
                suggestions.append("调整人声响度目标后再混音")

        final_mix = tracks["final_mix"]
        if final_mix and final_mix["ok"]:
            if final_mix["clipping_ratio"] > tolerances.clipping_ratio_warn or final_mix["peak"] > tolerances.peak_warn:
                issues.append(_issue("final_mix_clipping", "最终混音可能有爆音或顶峰", "high", final_mix["clipping_ratio"]))
                suggestions.append("降低混音总峰值或开启更强限幅")

        if context.active_ratio is not None and context.active_ratio < 0.35:
            issues.append(_issue("active_ratio_low", "目标歌曲有效人声占比偏低，转换段落可能不稳定", "low", context.active_ratio))
            suggestions.append("检查分离人声是否有过多空白或伴奏段")

        return {
            "analyzer": self.name,
            "status": "completed",
            "tracks": tracks,
            "issues": issues,
            "suggestions": _dedupe(suggestions),
        }


def _audio_stats(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    payload: dict[str, object] = {"path": str(path), "ok": False}
    if not path.exists():
        payload["error"] = "missing"
        return payload
    try:
        with wave.open(str(path), "rb") as handle:
            channels = handle.getnchannels()
            sample_rate = handle.getframerate()
            sample_width = handle.getsampwidth()
            frames = handle.getnframes()
            data = handle.readframes(frames)
        if sample_width != 2 or frames <= 0:
            payload["error"] = "unsupported_wav"
            return payload
        audio = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        if channels > 1:
            audio = audio.reshape(-1, channels).mean(axis=1)
        if audio.size == 0:
            payload["error"] = "empty"
            return payload
        abs_audio = np.abs(audio)
        rms = float(np.sqrt(np.mean(np.square(audio))) + 1e-12)
        peak = float(np.max(abs_audio))
        duration = float(audio.size / sample_rate)
        spectrum = np.abs(np.fft.rfft(audio[: min(audio.size, sample_rate * 60)]))
        freqs = np.fft.rfftfreq(spectrum.size * 2 - 2, 1.0 / sample_rate)
        total_energy = float(np.sum(spectrum) + 1e-12)
        low_ratio = float(np.sum(spectrum[freqs < 180]) / total_energy)
        high_ratio = float(np.sum(spectrum[freqs > 8000]) / total_energy)
        payload.update(
            {
                "ok": True,
                "duration_seconds": duration,
                "sample_rate": sample_rate,
                "channels": channels,
                "rms_dbfs": 20 * math.log10(rms),
                "peak": peak,
                "clipping_ratio": float(np.mean(abs_audio >= 0.985)),
                "silence_ratio": float(np.mean(abs_audio < 0.01)),
                "low_frequency_ratio": low_ratio,
                "high_frequency_ratio": high_ratio,
            }
        )
    except Exception as exc:
        payload["error"] = str(exc)
    return payload


def _issue(code: str, message: str, confidence: str, value: float) -> dict[str, object]:
    return {
        "code": code,
        "message": message,
        "confidence": confidence,
        "value": value,
    }


def _most_likely_issue(issues: list[dict[str, object]]) -> dict[str, object] | None:
    if not issues:
        return None
    priority = {"high": 3, "medium": 2, "low": 1}
    return max(issues, key=lambda issue: priority.get(str(issue.get("confidence")), 0))


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            output.append(item)
    return output
