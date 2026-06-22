"""Text reading endpoint helpers."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .tts import default_piper_model_from_env, synthesize_text_to_wav
from .web_generation import generate_song_payload
from .web_state import PROGRESS


def generate_tts_payload(
    *,
    seed_vc_dir: Path,
    fields: dict[str, Any],
    root: Path,
    output_dir: Path,
) -> dict[str, object]:
    text = str(fields.get("tts_text", "")).strip()
    voice_id = str(fields.get("voice_profile_id", "")).strip()
    engine_id = str(fields.get("engine_id", "seedvc")).strip() or "seedvc"
    if not voice_id:
        raise ValueError("请选择目标音色")
    if not text:
        raise ValueError("请输入要朗读的文字")

    provider = str(fields.get("tts_provider", "auto") or "auto")
    voice = str(fields.get("tts_voice", "Tingting") or "Tingting")
    rate = int(str(fields.get("tts_rate", "0") or "0"))
    length_scale = _float_field(fields, "tts_length_scale", 1.15, 0.6, 2.0)
    noise_scale = _float_field(fields, "tts_noise_scale", 0.667, 0.1, 1.5)
    noise_w_scale = _float_field(fields, "tts_noise_w_scale", 0.8, 0.1, 1.5)
    sentence_silence = _float_field(fields, "tts_sentence_silence", 0.25, 0.0, 2.0)
    volume = _float_field(fields, "tts_volume", 1.0, 0.2, 2.0)

    PROGRESS.reset("生成 TTS 朗读干声", 5, "running")
    tts_dir = root / "data" / "processed" / "web" / "tts"
    tts_wav = tts_dir / f"tts_{int(time.time())}.wav"
    tts_meta = synthesize_text_to_wav(
        text,
        tts_wav,
        voice=voice,
        rate=rate,
        provider=provider,
        piper_model=default_piper_model_from_env(),
        length_scale=length_scale,
        noise_scale=noise_scale,
        noise_w_scale=noise_w_scale,
        sentence_silence=sentence_silence,
        volume=volume,
    )
    PROGRESS.update("TTS 已生成，开始换成目标音色", 18)

    generation_fields: dict[str, object] = {
        "mode": str(fields.get("mode", "m2max_hq_30") or "m2max_hq_30"),
        "engine_id": engine_id,
        "voice_model_id": str(fields.get("voice_model_id", "") or ""),
        "skip_separation": True,
        "voice_profile_id": voice_id,
        "song_id": "",
        "save_voice": False,
        "save_song": False,
        "voice_name": "",
        "song_title": "文字朗读",
        "rights_confirmed": True,
        "rvc_preset": str(fields.get("rvc_preset", "stable_balanced") or "stable_balanced"),
        "diction_mode": str(fields.get("diction_mode", "off") or "off"),
        "vocal_style": str(fields.get("vocal_style", "neutral") or "neutral"),
        "allow_experimental_index": str(fields.get("allow_experimental_index", "")) == "on",
        "rvc_index_rate": str(fields.get("rvc_index_rate", "") or ""),
        "generate_variants": False,
        "pre_rvc_cleanup_mode": "off",
        "mix_style": "natural",
    }
    response = generate_song_payload(
        seed_vc_dir=seed_vc_dir,
        files={"song": tts_wav},
        fields=generation_fields,
        root=root,
        output_dir=output_dir,
    )
    metrics = response.get("metrics")
    if isinstance(metrics, dict):
        metrics["tts_text"] = text
        metrics["tts_provider"] = tts_meta["provider"]
        metrics["tts_voice"] = tts_meta["voice"]
        metrics["tts_length_scale"] = length_scale
        metrics["tts_noise_scale"] = noise_scale
        metrics["tts_noise_w_scale"] = noise_w_scale
        metrics["tts_sentence_silence"] = sentence_silence
        metrics["tts_volume"] = volume
        metrics["source_mode"] = "tts_clean_vocal"
    response["message"] = "文字朗读生成完成"
    response["tts"] = tts_meta
    return response


def _float_field(fields: dict[str, Any], key: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(str(fields.get(key, default) or default))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))
