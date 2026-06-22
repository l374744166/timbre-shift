"""Applio RVC training helpers."""

from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path
from typing import Callable

from .library import (
    DEFAULT_DB_PATH,
    DEFAULT_LIBRARY_DIR,
    VoiceModel,
    create_voice_model_record,
    get_voice_profile,
)
from .rvc_applio_dataset import prepare_applio_dataset
from .rvc_applio_runtime import _run_applio_python, check_applio, resolve_applio_dir


APPLIO_ENGINE_ID = "rvc_applio"


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
    epochs: int = 10,
    batch_size: int = 4,
    sample_rate: int = 40000,
    progress: Callable[[str, int], None] | None = None,
) -> VoiceModel:
    profile = get_voice_profile(voice_id, db_path=db_path)
    if not profile.allowed_as_target:
        raise PermissionError("这个音色没有授权为目标音色，不能训练 Applio RVC 模型")

    root = resolve_applio_dir(applio_dir)
    check = check_applio(root)
    if not check.available:
        raise RuntimeError(f"Applio RVC 未安装或未配置：{', '.join(check.missing)}")

    if progress:
        progress("准备 Applio RVC 数据集", 5)
    dataset = prepare_applio_dataset(
        voice_id,
        library_dir=library_dir,
        db_path=db_path,
        sample_rate=44100,
    )
    model_name = f"ts_{voice_id.replace('-', '_')}"
    applio_dataset = _copy_dataset_to_applio(dataset.dataset_path, model_name, root)

    start = time.perf_counter()
    wall_start = time.time()
    if progress:
        progress("检查 Applio RVC 训练资源", 10)

    def handle_output(line: str) -> None:
        if not progress:
            return
        epoch_match = re.search(r"\bepoch=(\d+)\b", line)
        if epoch_match:
            epoch = min(epochs, int(epoch_match.group(1)))
            percent = min(95, 20 + int(epoch / max(epochs, 1) * 72))
            progress(f"Applio RVC 训练第 {epoch}/{epochs} 轮", percent)
            return
        if "Training has been successfully completed" in line:
            progress("Applio RVC 正在导出模型", 96)
        elif "Saved model" in line:
            progress("Applio RVC 模型已保存", 98)

    code = f"""
import json
import shutil
from pathlib import Path
from core import run_extract_script, run_preprocess_script, run_prerequisites_script, run_train_script
import rvc.lib.tools.prerequisites_download as prerequisites

assets_config = Path("assets/config.json")
if not assets_config.exists():
    template = Path("assets/config_template.json")
    if not template.exists():
        raise FileNotFoundError("Applio 配置模板缺失: assets/config_template.json")
    assets_config.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template, assets_config)
config_data = json.loads(assets_config.read_text(encoding="utf-8"))
config_data.setdefault("model_author", "Timbre Shift")
assets_config.write_text(json.dumps(config_data, ensure_ascii=False, indent=2), encoding="utf-8")

# Timbre Shift trains Applio with HiFi-GAN by default. Applio's downloader also
# fetches RefineGAN files, but those are not needed for this path and are large
# enough to make first-time setup fragile on unstable HuggingFace connections.
prerequisites.pretraineds_refinegan_list = []
run_prerequisites_script(True, True, False)
required = [
    "rvc/models/predictors/rmvpe.pt",
    "rvc/models/embedders/contentvec/pytorch_model.bin",
    "rvc/models/embedders/contentvec/config.json",
    "rvc/models/pretraineds/hifi-gan/f0G{str(sample_rate)[:2]}k.pth",
    "rvc/models/pretraineds/hifi-gan/f0D{str(sample_rate)[:2]}k.pth",
]
missing = [path for path in required if not Path(path).exists()]
if missing:
    raise FileNotFoundError("Applio RVC 训练资源缺失: " + ", ".join(missing))
def ensure_step_ok(message, step):
    print(message)
    if "failed" in str(message).lower():
        raise RuntimeError(f"Applio RVC {{step}}失败: {{message}}")
msg = run_preprocess_script({model_name!r}, {str(applio_dataset)!r}, {sample_rate}, {os.cpu_count() or 4}, "Automatic", False, True, 0.5, 3.0, 0.3, "none")
ensure_step_ok(msg, "预处理")
msg = run_extract_script({model_name!r}, "rmvpe", {os.cpu_count() or 4}, "-", {sample_rate}, "contentvec", None, 2)
ensure_step_ok(msg, "抽特征")
feature_dir = Path("logs") / {model_name!r} / "extracted"
filelist = Path("logs") / {model_name!r} / "filelist.txt"
if not any(feature_dir.glob("*.npy")) or not filelist.exists() or filelist.stat().st_size == 0:
    raise RuntimeError("Applio RVC 抽特征没有生成训练特征；Mac 上请使用 CPU 抽特征，当前目录为空或 filelist 为空")
msg = run_train_script({model_name!r}, 10, True, True, {epochs}, {sample_rate}, {batch_size}, 0, True, 20, True, False, "Auto", False)
ensure_step_ok(msg, "训练")
"""
    _run_applio_python(root, code, on_output=handle_output)
    training_seconds = time.perf_counter() - start

    logs_dir = root / "logs" / model_name
    model_candidates = sorted(
        [path for path in logs_dir.glob(f"{model_name}_*.pth") if path.stat().st_mtime >= wall_start],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not model_candidates:
        model_candidates = sorted(
            [
                path
                for path in logs_dir.glob(f"{model_name}_{epochs}e_*.pth")
                if "manual" not in path.name
            ],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
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
