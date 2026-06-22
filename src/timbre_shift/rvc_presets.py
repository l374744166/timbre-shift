"""Stable RVC preset definitions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RVCPreset:
    id: str
    name: str
    index_rate: float
    protect: float
    pitch: int = 0
    f0_method: str = "rmvpe"
    clean_audio: bool = True
    diction_mode: str = "light"
    consonant_blend: float | None = None
    vocal_style: str = "neutral"
    risk_level: str = "stable"


RVC_PRESETS: dict[str, RVCPreset] = {
    "stable_balanced": RVCPreset(
        id="stable_balanced",
        name="自然稳定",
        index_rate=0.0,
        protect=0.40,
        diction_mode="light",
        vocal_style="neutral",
    ),
    "clear_diction": RVCPreset(
        id="clear_diction",
        name="歌词更清楚",
        index_rate=0.0,
        protect=0.50,
        diction_mode="medium",
        consonant_blend=0.06,
        vocal_style="close_intimate",
    ),
    "stronger_timbre_safe": RVCPreset(
        id="stronger_timbre_safe",
        name="更像目标音色",
        index_rate=0.0,
        protect=0.35,
        diction_mode="light",
        vocal_style="neutral",
    ),
    "experimental_index_light": RVCPreset(
        id="experimental_index_light",
        name="实验 index 轻度",
        index_rate=0.25,
        protect=0.40,
        diction_mode="light",
        vocal_style="neutral",
        risk_level="experimental",
    ),
    "experimental_index_medium": RVCPreset(
        id="experimental_index_medium",
        name="实验 index 中度",
        index_rate=0.45,
        protect=0.40,
        diction_mode="light",
        vocal_style="neutral",
        risk_level="high",
    ),
}


def get_rvc_preset(preset_id: str, allow_experimental_index: bool = False) -> RVCPreset:
    preset = RVC_PRESETS.get(preset_id) or RVC_PRESETS["stable_balanced"]
    if preset.index_rate > 0 and not allow_experimental_index:
        return RVC_PRESETS["stable_balanced"]
    return preset


def variant_preset_ids() -> list[str]:
    return ["stable_balanced", "clear_diction", "stronger_timbre_safe"]
