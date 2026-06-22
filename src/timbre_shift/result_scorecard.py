"""Human-readable result scorecards from generation metrics."""

from __future__ import annotations

from typing import Any


def build_result_scorecard(metrics: dict[str, Any]) -> list[dict[str, str]]:
    diagnostics = metrics.get("diagnostics") if isinstance(metrics.get("diagnostics"), dict) else {}
    issues = diagnostics.get("issues") if isinstance(diagnostics.get("issues"), list) else []
    issue_codes = {str(issue.get("code")) for issue in issues if isinstance(issue, dict)}
    peak = metrics.get("final_peak_after")
    active_ratio = metrics.get("active_ratio")
    diction_mode = str(metrics.get("diction_mode") or "")
    mix_style = str(metrics.get("mix_style") or "natural")

    cards = [
        _volume_card(peak, issue_codes, bool(metrics.get("clipping_prevented"))),
        _clarity_card(diction_mode, issue_codes),
        _blend_card(mix_style, peak),
        _source_card(active_ratio, issue_codes),
    ]
    return cards


def _volume_card(peak: object, issue_codes: set[str], clipping_prevented: bool) -> dict[str, str]:
    if isinstance(peak, (int, float)) and peak <= 0.95 and "final_mix_clipping" not in issue_codes:
        return {"label": "音量安全", "status": "好", "detail": "最终峰值安全，适合直接试听。"}
    if clipping_prevented:
        return {"label": "音量安全", "status": "已保护", "detail": "检测到偏满，已做防爆音处理。"}
    return {"label": "音量安全", "status": "偏满", "detail": "建议换自然/伴奏融合，或重新生成安全版。"}


def _clarity_card(diction_mode: str, issue_codes: set[str]) -> dict[str, str]:
    if "converted_harshness" in issue_codes:
        return {"label": "人声清晰", "status": "偏刺", "detail": "可试温暖厚实或柔和抒情。"}
    if diction_mode in {"medium", "strong"}:
        return {"label": "人声清晰", "status": "较清楚", "detail": "咬字已增强，注意是否带回原唱痕迹。"}
    return {"label": "人声清晰", "status": "自然", "detail": "如果歌词糊，可试歌词更清楚。"}


def _blend_card(mix_style: str, peak: object) -> dict[str, str]:
    if mix_style == "vocal_forward":
        return {"label": "伴奏融合", "status": "人声靠前", "detail": "适合展示音色，成品感可再试自然。"}
    if mix_style == "blend_with_backing":
        return {"label": "伴奏融合", "status": "融合", "detail": "整体更像成品歌，音色细节会低调一些。"}
    return {"label": "伴奏融合", "status": "平衡", "detail": "人声和伴奏比例较稳。"}


def _source_card(active_ratio: object, issue_codes: set[str]) -> dict[str, str]:
    if "source_vocal_low_residue" in issue_codes:
        return {"label": "源素材", "status": "有残留", "detail": "下次建议源人声清理设为标准。"}
    if isinstance(active_ratio, (int, float)) and active_ratio < 0.35:
        return {"label": "源素材", "status": "人声偏少", "detail": "歌曲有效人声少，转换段落可能不稳定。"}
    return {"label": "源素材", "status": "可用", "detail": "源人声比例正常。"}
