"""Readable output filenames for generated audio."""

from __future__ import annotations

import datetime as dt
import re
from typing import Any


PRESET_LABELS = {
    "stable_balanced": "自然稳定",
    "clear_diction": "歌词更清楚",
    "stronger_timbre_safe": "更像目标音色",
}


def build_output_basename(metrics: dict[str, Any] | None) -> str:
    payload = metrics or {}
    voice = str(payload.get("voice_profile_name") or "未命名音色")
    song = str(payload.get("song_title") or "未命名歌曲")
    preset = PRESET_LABELS.get(str(payload.get("rvc_preset") or ""), str(payload.get("rvc_preset") or "生成"))
    stamp = dt.datetime.now().strftime("%H%M")
    return "_".join(_clean_part(part) for part in [voice, song, preset, stamp] if part)


def _clean_part(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "-", value.strip())
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned[:28] or "未命名"
