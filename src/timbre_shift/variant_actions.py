"""Helpers for comparing and selecting generated variants."""

from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path
from typing import Any

from .web_utils import safe_filename


def find_variant(variant_id: str, metrics: dict[str, object]) -> dict[str, object] | None:
    for item in metrics.get("variants", []) if isinstance(metrics, dict) else []:
        if isinstance(item, dict) and str(item.get("id", "")) == variant_id:
            return item
    return None


def select_variant(output_dir: Path, variant_id: str) -> dict[str, Any]:
    if not variant_id:
        raise ValueError("没有选择对比版本")
    metrics = _read_metrics(output_dir)
    item = find_variant(variant_id, metrics)
    if not item:
        raise ValueError("找不到这个对比版本")

    source_wav = Path(str(item.get("wav", "")))
    source_mp3 = Path(str(item.get("mp3", "")))
    if not source_wav.exists():
        raise ValueError("对比版本 WAV 不存在")

    final_wav = output_dir / "final.wav"
    final_mp3 = output_dir / "final.mp3"
    shutil.copy2(source_wav, final_wav)
    if source_mp3.exists():
        shutil.copy2(source_mp3, final_mp3)

    metrics["selected_variant"] = variant_id
    metrics["selected_variant_path"] = str(final_wav)
    metrics["selected_variant_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    _write_metrics(output_dir, metrics)

    return {
        "message": "已设为最终版本",
        "download_mp3_url": f"/download/{final_mp3.name}" if final_mp3.exists() else None,
        "download_wav_url": f"/download/{final_wav.name}",
    }


def record_variant_feedback(output_dir: Path, variant_id: str) -> dict[str, str]:
    if not variant_id:
        raise ValueError("没有选择对比版本")
    metrics = _read_metrics(output_dir)
    item = find_variant(variant_id, metrics) or {}
    feedback = {
        "liked_variant": variant_id,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "preset": item.get("id") or variant_id,
        "diction_mode": item.get("diction_mode"),
        "vocal_style": item.get("vocal_style"),
        "rvc_index_rate": metrics.get("rvc_index_rate"),
    }
    (output_dir / "variant_feedback.json").write_text(
        json.dumps(feedback, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return {"message": "已记录喜欢的版本"}


def build_variant_downloads(metrics: dict[str, object]) -> list[dict[str, object]]:
    variants: list[dict[str, object]] = []
    for item in metrics.get("variants", []) if isinstance(metrics, dict) else []:
        if not isinstance(item, dict):
            continue
        mp3_path = Path(str(item.get("mp3", "")))
        wav_path = Path(str(item.get("wav", "")))
        if mp3_path.exists():
            variants.append(
                {
                    **item,
                    "download_url": f"/download/variants/{safe_filename(mp3_path.name)}",
                    "download_mp3_url": f"/download/variants/{safe_filename(mp3_path.name)}",
                    "download_wav_url": f"/download/variants/{safe_filename(wav_path.name)}" if wav_path.exists() else None,
                }
            )
    return variants


def _read_metrics(output_dir: Path) -> dict[str, object]:
    metrics_path = output_dir / "metrics.json"
    if not metrics_path.exists():
        return {}
    try:
        payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_metrics(output_dir: Path, metrics: dict[str, object]) -> None:
    metrics_path = output_dir / "metrics.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
