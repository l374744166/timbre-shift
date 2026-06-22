"""Applio RVC dataset preparation."""

from __future__ import annotations

import json
from pathlib import Path

from .audio import normalize_audio, probe_duration
from .library import DEFAULT_DB_PATH, DEFAULT_LIBRARY_DIR, get_voice_profile, list_voice_samples
from .rvc_mlx import RVCDatasetResult


APPLIO_ENGINE_ID = "rvc_applio"


def prepare_applio_dataset(
    voice_id: str,
    library_dir: Path = DEFAULT_LIBRARY_DIR,
    db_path: Path = DEFAULT_DB_PATH,
    sample_rate: int = 44100,
    min_segment_seconds: float = 2.0,
) -> RVCDatasetResult:
    profile = get_voice_profile(voice_id, db_path=db_path)
    if not profile.allowed_as_target:
        raise PermissionError("这个音色没有授权为目标音色，不能准备 Applio RVC 数据集")

    samples = list_voice_samples(voice_id, db_path=db_path)
    sources = [
        Path(sample.clean_audio_path or sample.raw_audio_path)
        for sample in samples
        if Path(sample.clean_audio_path or sample.raw_audio_path).exists()
    ]
    if not sources:
        raise ValueError("这个音色还没有可用声音素材")

    dataset_dir = library_dir / "voices" / voice_id / "rvc_applio" / "dataset"
    wav_dir = dataset_dir / "wavs"
    wav_dir.mkdir(parents=True, exist_ok=True)

    total_seconds = 0.0
    segment_count = 0
    source_files: list[str] = []
    for index, source in enumerate(sources, start=1):
        duration = probe_duration(source) or 0.0
        if duration < min_segment_seconds:
            continue
        target = wav_dir / f"sample_{index:04d}.wav"
        normalize_audio(source, target, sample_rate=sample_rate)
        converted_duration = probe_duration(target) or duration
        total_seconds += converted_duration
        segment_count += 1
        source_files.append(str(source))

    warnings: list[str] = []
    if total_seconds < 300:
        warnings.append("素材少于 5 分钟，只适合测试")
    if total_seconds < 600:
        warnings.append("建议 10 分钟以上低噪人声更稳定")
    if segment_count == 0:
        raise ValueError("没有足够长的声音片段可用于 Applio RVC 数据集")

    metadata = {
        "voice_id": voice_id,
        "engine_id": APPLIO_ENGINE_ID,
        "sample_rate": sample_rate,
        "total_seconds": total_seconds,
        "sample_count": len(sources),
        "segment_count": segment_count,
        "source_files": source_files,
        "warnings": warnings,
    }
    metadata_path = dataset_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return RVCDatasetResult(
        dataset_path=dataset_dir,
        metadata_path=metadata_path,
        total_seconds=total_seconds,
        sample_count=len(sources),
        segment_count=segment_count,
        source_files=source_files,
        warnings=warnings,
    )
