"""Applio RVC helpers.

Applio is kept as a local vendor checkout at ``vendor/applio``.  This module
isolates its training and inference entrypoints from the rest of Timbre Shift.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

from .rvc_applio_infer import convert_with_applio
from .rvc_applio_train import train_applio_model
from .rvc_applio_dataset import prepare_applio_dataset
from .rvc_applio_runtime import (
    ApplioCheck,
    ApplioCommandError,
    check_applio,
    resolve_applio_dir,
    resolve_applio_python,
)
from .library import (
    VoiceModel,
    sha256_file,
)


APPLIO_ENGINE_ID = "rvc_applio"
APPLIO_ENGINE_NAME = "Applio RVC"


def rvc_applio_cache_key(
    source_vocal: Path,
    voice_model: VoiceModel,
    options: dict[str, object],
) -> str:
    model_path = Path(voice_model.model_path)
    index_path = Path(voice_model.index_path) if voice_model.index_path else None
    payload = {
        "engine_id": APPLIO_ENGINE_ID,
        "source_vocal_hash": sha256_file(source_vocal),
        "voice_model_id": voice_model.id,
        "model_hash": sha256_file(model_path) if model_path.exists() else "",
        "index_hash": sha256_file(index_path) if index_path and index_path.exists() else "",
        "pitch_shift": int(options.get("pitch_shift", 0)),
        "f0_method": str(options.get("f0_method", "rmvpe")),
        "index_rate": float(options.get("index_rate", 0.0)),
        "protect": float(options.get("protect", 0.33)),
        "clean_audio": bool(options.get("clean_audio", True)),
        "clean_strength": float(options.get("clean_strength", 0.35)),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
