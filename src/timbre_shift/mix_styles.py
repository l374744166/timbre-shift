"""Simple mix style presets for final render."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MixStyle:
    id: str
    name: str
    vocal_gain: float
    backing_gain: float


MIX_STYLES: dict[str, MixStyle] = {
    "natural": MixStyle("natural", "自然", 1.0, 0.90),
    "vocal_forward": MixStyle("vocal_forward", "人声靠前", 1.05, 0.82),
    "blend_with_backing": MixStyle("blend_with_backing", "伴奏融合", 0.92, 0.95),
}


def get_mix_style(style_id: str | None) -> MixStyle:
    return MIX_STYLES.get(style_id or "") or MIX_STYLES["natural"]
