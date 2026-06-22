"""Training API helpers for the web UI."""

from __future__ import annotations

from .library import DEFAULT_DB_PATH, DEFAULT_LIBRARY_DIR, list_voice_samples
from .rvc_applio import prepare_applio_dataset, train_applio_model
from .web_state import PROGRESS


def prepare_applio_payload(fields: dict[str, object]) -> dict[str, object]:
    voice_id = _require_trainable_voice(fields)
    PROGRESS.reset("准备 Applio RVC 数据集", 5, "running")
    result = prepare_applio_dataset(
        voice_id,
        library_dir=DEFAULT_LIBRARY_DIR,
        db_path=DEFAULT_DB_PATH,
    )
    PROGRESS.update("Applio RVC 数据集已准备", 100, "completed")
    return {
        "dataset_path": str(result.dataset_path),
        "metadata_path": str(result.metadata_path),
        "total_seconds": result.total_seconds,
        "sample_count": result.sample_count,
        "segment_count": result.segment_count,
        "warnings": result.warnings,
        "message": "数据集已准备",
    }


def train_applio_payload(fields: dict[str, object]) -> dict[str, object]:
    voice_id = _require_trainable_voice(fields)
    epochs = int(fields.get("epochs", 10) or 10)
    if epochs < 1 or epochs > 120:
        raise ValueError("训练轮数需要在 1 到 120 之间")
    PROGRESS.reset("开始 Applio RVC 训练", 2, "running")
    model = train_applio_model(
        voice_id,
        library_dir=DEFAULT_LIBRARY_DIR,
        db_path=DEFAULT_DB_PATH,
        epochs=epochs,
        batch_size=4,
        sample_rate=40000,
        progress=lambda step, percent: PROGRESS.update(step, percent),
    )
    PROGRESS.update("Applio RVC 训练完成", 100, "completed")
    return {
        "id": model.id,
        "name": model.model_name,
        "model_path": model.model_path,
        "index_path": model.index_path,
        "dataset_seconds": model.dataset_seconds,
        "training_seconds": model.training_seconds,
        "status": model.status,
        "message": "训练完成",
    }


def _require_trainable_voice(fields: dict[str, object]) -> str:
    voice_id = str(fields.get("voice_profile_id", "")).strip()
    if not voice_id:
        raise ValueError("先选择一个已保存音色")
    if not list_voice_samples(voice_id, db_path=DEFAULT_DB_PATH):
        raise ValueError("这个音色库还没有训练素材，请先上传目标歌手训练素材")
    return voice_id
