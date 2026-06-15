"""Applio RVC helpers.

Applio is kept as a local vendor checkout at ``vendor/applio``.  This module
isolates its training and inference entrypoints from the rest of Timbre Shift.
"""

from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .audio import normalize_audio, probe_duration
from .engines.base import EngineResult
from .library import (
    DEFAULT_DB_PATH,
    DEFAULT_LIBRARY_DIR,
    VoiceModel,
    create_voice_model_record,
    get_voice_profile,
    list_voice_samples,
    sha256_file,
)
from .rvc_mlx import RVCDatasetResult


APPLIO_ENGINE_ID = "rvc_applio"
APPLIO_ENGINE_NAME = "Applio RVC"
DEFAULT_APPLIO_DIR = Path("vendor/applio")


@dataclass(frozen=True)
class ApplioCheck:
    available: bool
    applio_dir: Path
    python: Path | None
    missing: list[str]


def resolve_applio_dir(applio_dir: Path | None = None) -> Path:
    return Path(os.environ.get("APPLIO_DIR") or applio_dir or DEFAULT_APPLIO_DIR).resolve()


def resolve_applio_python(applio_dir: Path) -> Path | None:
    env_python = os.environ.get("APPLIO_PYTHON")
    if env_python:
        return Path(env_python)
    candidates = [
        applio_dir / ".venv" / "bin" / "python",
        applio_dir / ".venv" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def check_applio(applio_dir: Path | None = None) -> ApplioCheck:
    root = resolve_applio_dir(applio_dir)
    missing: list[str] = []
    if not (root / "core.py").exists():
        missing.append(f"{root}/core.py")
    if not (root / "rvc" / "infer" / "infer.py").exists():
        missing.append(f"{root}/rvc/infer/infer.py")
    if not (root / "rvc" / "train" / "train.py").exists():
        missing.append(f"{root}/rvc/train/train.py")

    python = resolve_applio_python(root)
    if python is None or not python.exists():
        missing.append("APPLIO_PYTHON or vendor/applio/.venv/bin/python")

    return ApplioCheck(
        available=not missing,
        applio_dir=root,
        python=python if python and python.exists() else None,
        missing=missing,
    )


def rvc_applio_cache_key(
    source_vocal: Path,
    voice_model: VoiceModel,
    options: dict[str, object],
) -> str:
    model_path = Path(voice_model.model_path)
    index_path = Path(voice_model.index_path) if voice_model.index_path else None
    payload = {
        "engine_id": APPLIO_ENGINE_ID,
        "source_vocal_hash": sha256_file(source_vocal),
        "voice_model_id": voice_model.id,
        "model_hash": sha256_file(model_path) if model_path.exists() else "",
        "index_hash": sha256_file(index_path) if index_path and index_path.exists() else "",
        "pitch_shift": int(options.get("pitch_shift", 0)),
        "f0_method": str(options.get("f0_method", "rmvpe")),
        "index_rate": float(options.get("index_rate", 0.75)),
        "protect": float(options.get("protect", 0.33)),
        "clean_audio": bool(options.get("clean_audio", True)),
        "clean_strength": float(options.get("clean_strength", 0.35)),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


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


def _run_applio_python(applio_dir: Path, code: str) -> None:
    check = check_applio(applio_dir)
    if not check.python:
        raise RuntimeError("Applio Python 环境不存在，请先在 vendor/applio 运行 ./run-install.sh")
    env = os.environ.copy()
    env.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    env.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.0")
    command = [str(check.python), "-c", code]
    try:
        subprocess.run(command, cwd=applio_dir, env=env, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Applio RVC 命令失败：{exc}") from exc


def _copy_dataset_to_applio(dataset_path: Path, model_name: str, applio_dir: Path) -> Path:
    source_wavs = dataset_path / "wavs"
    if not source_wavs.exists():
        raise FileNotFoundError(f"Applio RVC 数据集不存在：{source_wavs}")
    target = applio_dir / "assets" / "datasets" / model_name
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    for source in sorted(source_wavs.glob("*.wav")):
        shutil.copy2(source, target / source.name)
    return target


def train_applio_model(
    voice_id: str,
    library_dir: Path = DEFAULT_LIBRARY_DIR,
    db_path: Path = DEFAULT_DB_PATH,
    applio_dir: Path | None = None,
    epochs: int = 120,
    batch_size: int = 4,
    sample_rate: int = 40000,
) -> VoiceModel:
    profile = get_voice_profile(voice_id, db_path=db_path)
    if not profile.allowed_as_target:
        raise PermissionError("这个音色没有授权为目标音色，不能训练 Applio RVC 模型")

    root = resolve_applio_dir(applio_dir)
    check = check_applio(root)
    if not check.available:
        raise RuntimeError(f"Applio RVC 未安装或未配置：{', '.join(check.missing)}")

    dataset = prepare_applio_dataset(
        voice_id,
        library_dir=library_dir,
        db_path=db_path,
        sample_rate=44100,
    )
    model_name = f"ts_{voice_id.replace('-', '_')}"
    applio_dataset = _copy_dataset_to_applio(dataset.dataset_path, model_name, root)

    start = time.perf_counter()
    code = f"""
from core import run_extract_script, run_preprocess_script, run_prerequisites_script, run_train_script
run_prerequisites_script(True, True, False)
msg = run_preprocess_script({model_name!r}, {str(applio_dataset)!r}, {sample_rate}, {os.cpu_count() or 4}, "Automatic", False, True, 0.5, 3.0, 0.3, "none")
print(msg)
msg = run_extract_script({model_name!r}, "rmvpe", {os.cpu_count() or 4}, 0, {sample_rate}, "contentvec", None, 2)
print(msg)
msg = run_train_script({model_name!r}, 10, True, True, {epochs}, {sample_rate}, {batch_size}, 0, True, 20, True, False, "Auto", False)
print(msg)
"""
    _run_applio_python(root, code)
    training_seconds = time.perf_counter() - start

    logs_dir = root / "logs" / model_name
    model_candidates = sorted(logs_dir.glob(f"{model_name}_*.pth"), key=lambda p: p.stat().st_mtime, reverse=True)
    index_candidates = sorted(logs_dir.glob("*.index"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not model_candidates:
        raise FileNotFoundError(f"Applio RVC 训练完成但没有找到模型：{logs_dir}")
    model_path = model_candidates[0]
    index_path = index_candidates[0] if index_candidates else None

    return create_voice_model_record(
        voice_id=voice_id,
        engine_id=APPLIO_ENGINE_ID,
        model_name=f"{profile.name} - Applio RVC",
        model_path=model_path,
        index_path=index_path,
        dataset_path=dataset.dataset_path,
        training_seconds=training_seconds,
        dataset_seconds=dataset.total_seconds,
        metadata={
            "applio_dir": str(root),
            "applio_model_name": model_name,
            "sample_rate": sample_rate,
            "epochs": epochs,
            "batch_size": batch_size,
            "warnings": dataset.warnings,
        },
        db_path=db_path,
    )


def convert_with_applio(
    source_vocal: Path,
    model_path: Path,
    output_dir: Path,
    options: dict[str, object],
    engine_id: str = APPLIO_ENGINE_ID,
    engine_name: str = APPLIO_ENGINE_NAME,
) -> EngineResult:
    start = time.perf_counter()
    source_vocal = source_vocal.resolve()
    model_path = model_path.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "converted-applio.wav"
    root = resolve_applio_dir(Path(str(options["applio_dir"])) if options.get("applio_dir") else None)
    check = check_applio(root)
    if not check.available:
        raise RuntimeError(f"Applio RVC 未安装或未配置：{', '.join(check.missing)}")

    index_path = options.get("index_path")
    code = f"""
from core import run_infer_script
_, written = run_infer_script(
    pitch={int(options.get("pitch_shift", 0))},
    index_rate={float(options.get("index_rate", 0.75))},
    volume_envelope={float(options.get("volume_envelope", 1.0))},
    protect={float(options.get("protect", 0.33))},
    f0_method={str(options.get("f0_method", "rmvpe"))!r},
    input_path={str(source_vocal)!r},
    output_path={str(output)!r},
    pth_path={str(model_path)!r},
    index_path={str(index_path or "")!r},
    split_audio={bool(options.get("split_audio", False))!r},
    f0_autotune={bool(options.get("f0_autotune", False))!r},
    f0_autotune_strength={float(options.get("f0_autotune_strength", 1.0))},
    proposed_pitch={bool(options.get("proposed_pitch", False))!r},
    proposed_pitch_threshold={float(options.get("proposed_pitch_threshold", 155.0))},
    clean_audio={bool(options.get("clean_audio", True))!r},
    clean_strength={float(options.get("clean_strength", 0.35))},
    export_format="WAV",
    embedder_model={str(options.get("embedder_model", "contentvec"))!r},
)
print(written)
"""
    _run_applio_python(root, code)
    if not output.exists():
        raise FileNotFoundError(f"Applio RVC did not write output: {output}")
    return EngineResult(
        converted_vocal_path=output,
        engine_id=engine_id,
        engine_name=engine_name,
        seconds=time.perf_counter() - start,
        device="mps",
        cache_hit=False,
        metadata={"model_path": str(model_path), "index_path": str(index_path) if index_path else None},
    )
