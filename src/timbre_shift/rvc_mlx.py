"""Experimental RVC-MLX helpers.

This module keeps RVC-MLX integration isolated from the stable Seed-VC path.
The dataset and cache helpers are implemented now; the actual third-party
training/inference command is intentionally adapter-driven because RVC-MLX
implementations differ.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .audio import normalize_audio, probe_duration
from .commands import as_strs, run_command
from .engines.base import EngineResult
from .library import (
    DEFAULT_DB_PATH,
    DEFAULT_LIBRARY_DIR,
    VoiceModel,
    get_voice_profile,
    list_voice_samples,
    sha256_file,
)


@dataclass(frozen=True)
class RVCDatasetResult:
    dataset_path: Path
    metadata_path: Path
    total_seconds: float
    sample_count: int
    segment_count: int
    source_files: list[str]
    warnings: list[str]


def rvc_mlx_cache_key(
    source_vocal: Path,
    voice_model: VoiceModel,
    options: dict[str, object],
) -> str:
    model_path = Path(voice_model.model_path)
    index_path = Path(voice_model.index_path) if voice_model.index_path else None
    payload = {
        "engine_id": "rvc_mlx",
        "source_vocal_hash": sha256_file(source_vocal),
        "voice_model_id": voice_model.id,
        "model_hash": sha256_file(model_path) if model_path.exists() else "",
        "index_hash": sha256_file(index_path) if index_path and index_path.exists() else "",
        "pitch_shift": int(options.get("pitch_shift", 0)),
        "f0_method": str(options.get("f0_method", "rmvpe")),
        "index_rate": float(options.get("index_rate", 0.75)),
        "protect": float(options.get("protect", 0.33)),
        "filter_radius": int(options.get("filter_radius", 3)),
        "resample_sr": int(options.get("resample_sr", 0)),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def prepare_rvc_mlx_dataset(
    voice_id: str,
    library_dir: Path = DEFAULT_LIBRARY_DIR,
    db_path: Path = DEFAULT_DB_PATH,
    sample_rate: int = 44100,
    min_segment_seconds: float = 2.0,
) -> RVCDatasetResult:
    profile = get_voice_profile(voice_id, db_path=db_path)
    if not profile.allowed_as_target:
        raise PermissionError("这个音色没有授权为目标音色，不能准备 RVC-MLX 数据集")

    samples = list_voice_samples(voice_id, db_path=db_path)
    sources = [
        Path(sample.clean_audio_path or sample.raw_audio_path)
        for sample in samples
        if Path(sample.clean_audio_path or sample.raw_audio_path).exists()
    ]
    if not sources:
        raise ValueError("这个音色还没有可用声音素材")

    dataset_dir = library_dir / "voices" / voice_id / "rvc_mlx" / "dataset"
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
        raise ValueError("没有足够长的声音片段可用于 RVC-MLX 数据集")

    metadata = {
        "voice_id": voice_id,
        "engine_id": "rvc_mlx",
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


def train_rvc_mlx_model(
    voice_id: str,
    library_dir: Path = DEFAULT_LIBRARY_DIR,
    db_path: Path = DEFAULT_DB_PATH,
) -> VoiceModel:
    profile = get_voice_profile(voice_id, db_path=db_path)
    if not profile.allowed_as_target:
        raise PermissionError("这个音色没有授权为目标音色，不能训练 RVC-MLX 模型")

    dataset_dir = library_dir / "voices" / voice_id / "rvc_mlx" / "dataset"
    metadata_path = dataset_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError("RVC-MLX 数据集不存在，请先运行 prepare-dataset")
    raise NotImplementedError(
        "RVC-MLX 训练命令还没有适配。请安装/选择具体 RVC-MLX 实现后，在 rvc_mlx.py 的 train_rvc_mlx_model 中接入命令。"
    )


def convert_with_rvc_mlx(
    source_vocal: Path,
    model_path: Path,
    output_dir: Path,
    options: dict[str, object],
    engine_id: str = "rvc_mlx",
    engine_name: str = "RVC-MLX Experimental",
) -> EngineResult:
    start = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "converted-rvc-mlx.wav"

    command = os.environ.get("RVC_MLX_COMMAND")
    if not command:
        raise RuntimeError("RVC-MLX 未安装或未配置：请设置 RVC_MLX_COMMAND 后再使用 rvc_mlx 引擎")

    args = [
        command,
        "--model",
        model_path,
        "--input",
        source_vocal,
        "--output",
        output,
    ]
    index_path = options.get("index_path")
    if index_path:
        args.extend(["--index", Path(str(index_path))])
    args.extend(["--pitch", int(options.get("pitch_shift", 0))])
    try:
        run_command(as_strs(args))
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"RVC-MLX 推理失败：{exc}") from exc

    if not output.exists():
        raise FileNotFoundError(f"RVC-MLX did not write output: {output}")
    return EngineResult(
        converted_vocal_path=output,
        engine_id=engine_id,
        engine_name=engine_name,
        seconds=time.perf_counter() - start,
        device="mlx",
        cache_hit=False,
        metadata={"model_path": str(model_path), "index_path": str(index_path) if index_path else None},
    )
