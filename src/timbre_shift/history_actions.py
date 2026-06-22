"""Actions for restoring and deleting generation history jobs."""

from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path
from typing import Any


def restore_history_job(history_root: Path, output_dir: Path, job_id: str) -> dict[str, Any]:
    job_dir = _job_dir(history_root, job_id)
    final_wav = job_dir / "final.wav"
    final_mp3 = job_dir / "final.mp3"
    dry_vocal_wav = job_dir / "dry_vocal.wav"
    dry_vocal_mp3 = job_dir / "dry_vocal.mp3"
    if not final_wav.exists():
        raise ValueError("这条历史没有 WAV 文件")

    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(final_wav, output_dir / "final.wav")
    if final_mp3.exists():
        shutil.copy2(final_mp3, output_dir / "final.mp3")
    if dry_vocal_wav.exists():
        shutil.copy2(dry_vocal_wav, output_dir / "dry_vocal.wav")
    if dry_vocal_mp3.exists():
        shutil.copy2(dry_vocal_mp3, output_dir / "dry_vocal.mp3")

    metrics_path = job_dir / "metrics.json"
    if metrics_path.exists():
        shutil.copy2(metrics_path, output_dir / "metrics.json")
        metrics = _read_json(output_dir / "metrics.json")
        metrics["restored_from_history"] = job_id
        metrics["restored_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        (output_dir / "metrics.json").write_text(
            json.dumps(metrics, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return {
        "message": "已设为当前最终版本",
        "download_mp3_url": "/download/final.mp3" if final_mp3.exists() else None,
        "download_wav_url": "/download/final.wav",
        "dry_vocal_download_mp3_url": "/download/dry_vocal.mp3" if dry_vocal_mp3.exists() else None,
        "dry_vocal_download_wav_url": "/download/dry_vocal.wav" if dry_vocal_wav.exists() else None,
    }


def delete_history_job(history_root: Path, job_id: str) -> dict[str, str]:
    job_dir = _job_dir(history_root, job_id)
    shutil.rmtree(job_dir)
    return {"message": "历史记录已删除"}


def _job_dir(history_root: Path, job_id: str) -> Path:
    if not job_id.startswith("job_"):
        raise ValueError("找不到这条生成历史")
    job_dir = history_root / job_id
    if not job_dir.is_dir():
        raise ValueError("找不到这条生成历史")
    return job_dir


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}
