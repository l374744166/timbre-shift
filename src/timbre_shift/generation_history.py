"""Archive generated outputs into timestamped history jobs."""

from __future__ import annotations

import datetime as dt
import json
import shutil
import uuid
from pathlib import Path
from typing import Any


def archive_generation_history(
    output_dir: Path,
    metrics: dict[str, Any],
    *,
    voice_profile_id: str | None,
    voice_profile_name: str | None,
    song_id: str | None,
    song_title: str | None,
    engine_id: str,
    render_mode: str,
) -> Path:
    created_at = dt.datetime.now(dt.timezone.utc)
    job_id = f"job_{created_at.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    history_dir = output_dir.parent / "history" / job_id
    history_dir.mkdir(parents=True, exist_ok=True)

    for filename in ["final.wav", "final.mp3", "dry_vocal.wav", "dry_vocal.mp3", "metrics.json", "variant_feedback.json"]:
        source = output_dir / filename
        if source.exists():
            shutil.copy2(source, history_dir / filename)

    variants_dir = output_dir / "variants"
    if variants_dir.exists():
        target_variants = history_dir / "variants"
        if target_variants.exists():
            shutil.rmtree(target_variants)
        shutil.copytree(variants_dir, target_variants)

    source_info = {
        "voice_profile_id": voice_profile_id,
        "voice_profile_name": voice_profile_name,
        "song_id": song_id,
        "song_title": song_title,
        "engine_id": engine_id,
        "render_mode": render_mode,
        "rvc_preset": metrics.get("rvc_preset"),
        "diction_mode": metrics.get("diction_mode"),
        "vocal_style": metrics.get("vocal_style"),
        "pre_rvc_cleanup_mode": metrics.get("pre_rvc_cleanup_mode"),
        "mix_style": metrics.get("mix_style"),
        "selected_variant": metrics.get("selected_variant"),
        "created_at": created_at.isoformat(),
    }
    (history_dir / "source_info.json").write_text(
        json.dumps(source_info, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return history_dir


def list_generation_history(history_root: Path, limit: int = 12) -> list[dict[str, Any]]:
    if not history_root.exists():
        return []
    jobs: list[dict[str, Any]] = []
    for job_dir in sorted(history_root.glob("job_*"), reverse=True):
        if not job_dir.is_dir():
            continue
        source_info = {}
        metrics = {}
        try:
            source_info = json.loads((job_dir / "source_info.json").read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        try:
            metrics = json.loads((job_dir / "metrics.json").read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        jobs.append(
            {
                "id": job_dir.name,
                "created_at": source_info.get("created_at"),
                "voice_profile_name": source_info.get("voice_profile_name"),
                "song_title": source_info.get("song_title"),
                "engine_id": source_info.get("engine_id"),
                "render_mode": source_info.get("render_mode"),
                "rvc_preset": source_info.get("rvc_preset") or metrics.get("rvc_preset"),
                "diction_mode": source_info.get("diction_mode") or metrics.get("diction_mode"),
                "vocal_style": source_info.get("vocal_style") or metrics.get("vocal_style"),
                "pre_rvc_cleanup_mode": source_info.get("pre_rvc_cleanup_mode") or metrics.get("pre_rvc_cleanup_mode"),
                "mix_style": source_info.get("mix_style") or metrics.get("mix_style"),
                "selected_variant": source_info.get("selected_variant") or metrics.get("selected_variant"),
                "final_peak_after": metrics.get("final_peak_after"),
                "clipping_prevented": metrics.get("clipping_prevented"),
                "diagnostic_summary": (metrics.get("diagnostics") or {}).get("most_likely_issue")
                if isinstance(metrics.get("diagnostics"), dict)
                else None,
                "total_seconds": metrics.get("total_seconds"),
                "has_mp3": (job_dir / "final.mp3").exists(),
                "has_wav": (job_dir / "final.wav").exists(),
                "has_dry_vocal_mp3": (job_dir / "dry_vocal.mp3").exists(),
                "has_dry_vocal_wav": (job_dir / "dry_vocal.wav").exists(),
            }
        )
        if len(jobs) >= limit:
            break
    return jobs
