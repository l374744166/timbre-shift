"""Small response serializers used by the web API."""

from __future__ import annotations

import json
from typing import Any


SOURCE_LABELS = {
    "upload_voice": "干净人声",
    "clean_voice": "干净人声",
    "mixed_voice": "带伴奏素材",
    "separated_voice": "分离人声",
    "separated_compact_voice": "分离后有效人声",
}


def serialize_voice_sample(sample: object) -> dict[str, object]:
    source_type = str(getattr(sample, "source_type", "") or "")
    return {
        "id": getattr(sample, "id", ""),
        "name": getattr(sample, "name", None) or "未命名素材",
        "source_type": source_type,
        "source_label": SOURCE_LABELS.get(source_type, source_type or "素材"),
        "duration_seconds": getattr(sample, "duration_seconds", None),
        "quality_score": getattr(sample, "quality_score", None),
        "noise_score": getattr(sample, "noise_score", None),
        "created_at": getattr(sample, "created_at", None),
    }


def serialize_voice_model(model: object, quality: dict[str, Any]) -> dict[str, object]:
    metadata: dict[str, Any] = {}
    raw_metadata = getattr(model, "metadata_json", None)
    if raw_metadata:
        try:
            loaded = json.loads(str(raw_metadata))
            metadata = loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            metadata = {}
    epochs = metadata.get("epochs")
    if not epochs:
        model_path = str(getattr(model, "model_path", "") or "")
        marker = model_path.rsplit("/", 1)[-1]
        for part in marker.replace(".", "_").split("_"):
            if part.endswith("e") and part[:-1].isdigit():
                epochs = int(part[:-1])
                break
    return {
        "id": getattr(model, "id", ""),
        "name": getattr(model, "model_name", ""),
        "engine_id": getattr(model, "engine_id", ""),
        "status": getattr(model, "status", ""),
        "epochs": epochs,
        "batch_size": metadata.get("batch_size"),
        "sample_rate": metadata.get("sample_rate"),
        "dataset_seconds": getattr(model, "dataset_seconds", None),
        "training_seconds": getattr(model, "training_seconds", None),
        "model_path": getattr(model, "model_path", None),
        "updated_at": getattr(model, "updated_at", None),
        "sample_count": quality["sample_count"],
        "sample_seconds": quality["sample_seconds"],
        "quality_hint": quality["duration_hint"],
        "quality_details": quality,
    }
