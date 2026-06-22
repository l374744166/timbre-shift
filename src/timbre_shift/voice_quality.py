"""Voice sample quality summaries for the web UI."""

from __future__ import annotations

from typing import Any


def build_voice_quality_details(samples: list[Any]) -> dict[str, object]:
    sample_count = len(samples)
    sample_seconds = sum(float(getattr(sample, "duration_seconds", 0.0) or 0.0) for sample in samples)
    source_types = {str(getattr(sample, "source_type", "") or "") for sample in samples}
    if sample_seconds < 300:
        duration_hint = "素材少于5分钟，只适合测试，风格和咬字不稳定"
    elif sample_seconds < 600:
        duration_hint = "素材5-10分钟，可用但不稳"
    elif sample_seconds < 1800:
        duration_hint = "素材10-30分钟，比较推荐"
    else:
        duration_hint = "素材超过30分钟，更稳"

    clean_sources = {"clean_voice", "upload_voice", "clean_vocal"}
    separated_sources = {"mixed_voice", "separated_voice", "separated_compact_voice"}
    warnings: list[str] = []
    if sample_count <= 1:
        warnings.append("素材来源偏单一，可能只学到一首歌的质感")
    if sample_seconds < 600:
        warnings.append("建议补到10-30分钟，会更稳")
    if not (source_types & clean_sources):
        warnings.append("建议加入干净人声或清唱素材")
    if source_types & separated_sources:
        warnings.append("分离人声可用，但残留伴奏会影响训练")

    return {
        "sample_count": sample_count,
        "sample_seconds": sample_seconds,
        "source_types": sorted(source_types),
        "duration_hint": duration_hint,
        "warnings": warnings,
    }
