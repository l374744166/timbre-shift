"""Per-voice generation preference storage."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

DEFAULT_PREFERENCES_PATH = Path("data/library/voice_preferences.json")


PREFERENCE_FIELDS = {
    "voice_profile_id",
    "engine_id",
    "rvc_goal",
    "diction_mode",
    "vocal_style",
    "rvc_index_enabled",
    "rvc_index_rate",
    "mix_style",
    "pre_rvc_cleanup_mode",
    "selected_variant",
}


def load_voice_preferences(path: Path = DEFAULT_PREFERENCES_PATH) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def get_voice_preference(voice_profile_id: str, path: Path = DEFAULT_PREFERENCES_PATH) -> dict[str, Any] | None:
    if not voice_profile_id:
        return None
    preferences = load_voice_preferences(path)
    item = preferences.get(voice_profile_id)
    return item if isinstance(item, dict) else None


def save_voice_preference(
    voice_profile_id: str,
    preference: dict[str, Any],
    path: Path = DEFAULT_PREFERENCES_PATH,
) -> dict[str, Any]:
    if not voice_profile_id:
        raise ValueError("Missing voice_profile_id")
    preferences = load_voice_preferences(path)
    cleaned = {key: preference.get(key) for key in PREFERENCE_FIELDS if key in preference}
    cleaned["voice_profile_id"] = voice_profile_id
    cleaned["timestamp"] = dt.datetime.now(dt.timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    preferences[voice_profile_id] = cleaned
    path.write_text(json.dumps(preferences, indent=2, ensure_ascii=False), encoding="utf-8")
    return cleaned
