"""Result payload and lightweight test-output helpers for the web UI."""

from __future__ import annotations

import json
import math
import wave
from pathlib import Path

from .download_names import build_output_basename
from .result_scorecard import build_result_scorecard
from .variant_actions import build_variant_downloads


def read_metrics_payload(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def build_generation_response(
    output_dir: Path,
    final_mix: Path,
    metrics_payload: dict[str, object],
    *,
    render_mode: str,
    engine_id: str,
    fields: dict[str, object],
) -> dict[str, object]:
    final_mp3 = output_dir / "final.mp3"
    dry_vocal_mp3 = output_dir / "dry_vocal.mp3"
    dry_vocal_wav = output_dir / "dry_vocal.wav"
    output_basename = build_output_basename(metrics_payload)
    return {
        "download_url": f"/download/{final_mp3.name if final_mp3.exists() else final_mix.name}",
        "download_mp3_url": f"/download/{final_mp3.name}" if final_mp3.exists() else None,
        "download_wav_url": f"/download/{final_mix.name}",
        "dry_vocal_download_mp3_url": f"/download/{dry_vocal_mp3.name}" if dry_vocal_mp3.exists() else None,
        "dry_vocal_download_wav_url": f"/download/{dry_vocal_wav.name}" if dry_vocal_wav.exists() else None,
        "mp3_filename": f"{output_basename}.mp3" if final_mp3.exists() else None,
        "wav_filename": f"{output_basename}.wav",
        "dry_vocal_mp3_filename": f"{output_basename}_干声.mp3" if dry_vocal_mp3.exists() else None,
        "dry_vocal_wav_filename": f"{output_basename}_干声.wav" if dry_vocal_wav.exists() else None,
        "output_basename": output_basename,
        "scorecard": build_result_scorecard(metrics_payload),
        "mode": "real",
        "message": "歌曲生成完成",
        "render_mode": render_mode,
        "engine_id": engine_id,
        "voice_model_id": fields["voice_model_id"],
        "skip_separation": fields["skip_separation"],
        "voice_profile_id": fields["voice_profile_id"],
        "song_id": fields["song_id"],
        "metrics": metrics_payload,
        "variants": build_variant_downloads(metrics_payload),
    }


def write_error_metrics(path: Path, error: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "voice_profile_id": None,
                "voice_profile_name": None,
                "song_id": None,
                "song_title": None,
                "render_mode": None,
                "source_mode": None,
                "library_voice_hit": False,
                "library_song_stems_hit": False,
                "demucs_cache_hit": False,
                "seedvc_cache_hit": False,
                "song_duration_seconds": None,
                "active_vocal_seconds": None,
                "active_ratio": None,
                "prepare_voice_seconds": 0.0,
                "prepare_song_seconds": 0.0,
                "demucs_seconds": 0.0,
                "vocal_segment_detect_seconds": 0.0,
                "seedvc_seconds": 0.0,
                "restore_timeline_seconds": 0.0,
                "mix_seconds": 0.0,
                "mp3_export_seconds": 0.0,
                "total_seconds": 0.0,
                "seedvc_rtf": None,
                "mps_requested": False,
                "mps_used": False,
                "seedvc_device": None,
                "seedvc_cpu_fallback_used": False,
                "output_wav": None,
                "output_mp3": None,
                "error_message": error,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def create_test_result(path: Path) -> Path:
    """Create a short WAV so the upload/download flow is immediately testable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 44100
    duration_seconds = 3
    frequency = 440.0
    amplitude = 12000
    total_frames = sample_rate * duration_seconds

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for index in range(total_frames):
            sample = int(amplitude * math.sin(2 * math.pi * frequency * index / sample_rate))
            wav.writeframesraw(sample.to_bytes(2, byteorder="little", signed=True))
    return path
