"""Read-only web API payload builders."""

from __future__ import annotations

from .library import DEFAULT_DB_PATH, list_voice_models, list_voice_samples
from .voice_preferences import get_voice_preference
from .voice_quality import build_voice_quality_details
from .web_serializers import serialize_voice_model, serialize_voice_sample


def voice_preference_payload(voice_id: str) -> dict[str, object]:
    return {"preference": get_voice_preference(voice_id)}


def voice_samples_payload(voice_id: str) -> dict[str, object]:
    if not voice_id:
        return {"samples": [], "sample_count": 0}
    samples = list_voice_samples(voice_id, db_path=DEFAULT_DB_PATH)
    return {
        "samples": [serialize_voice_sample(sample) for sample in samples],
        "sample_count": len(samples),
    }


def voice_models_payload(voice_id: str, engine_id: str) -> dict[str, object]:
    if not voice_id:
        return {"models": []}
    samples = list_voice_samples(voice_id, db_path=DEFAULT_DB_PATH)
    quality = build_voice_quality_details(samples)
    models = [
        serialize_voice_model(model, quality)
        for model in list_voice_models(voice_id, engine_id=engine_id, db_path=DEFAULT_DB_PATH)
    ]
    return {"models": models}
