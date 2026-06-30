"""Voice conversion stage orchestration for Seed-VC and trained RVC engines."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .library import get_voice_model, get_voice_model_by_id
from .pipeline_config import PipelineOptions, RenderPreset, seedvc_chunk_settings
from .pipeline_seedvc import _convert_seedvc_chunked, _convert_seedvc_whole

ProgressCallback = Callable[[str, int], None]


@dataclass(frozen=True)
class ConversionStageResult:
    converted_vocal: Path
    voice_model: object | None = None
    rvc_convert_options: dict[str, object] | None = None


def convert_source_vocal(
    *,
    options: PipelineOptions,
    preset: RenderPreset,
    engine,
    engine_check: dict,
    source_vocal: Path,
    conversion_source_vocal: Path,
    prepared_voice: Path,
    converted_dir: Path,
    actual_device: str,
    voice_profile,
    rvc_preset,
    effective_rvc_index_rate: float,
    cache_label: str,
    metrics: dict[str, object],
    update: ProgressCallback,
) -> ConversionStageResult:
    update(f"转换为目标音色（{engine.name}，{cache_label}）", 70)
    if options.engine_id == "seedvc":
        allow_cpu_fallback = preset.clip_seconds is not None and preset.clip_seconds <= 15
        chunk_seconds, chunk_workers = seedvc_chunk_settings(options, preset)
        metrics["seedvc_chunk_seconds"] = chunk_seconds
        metrics["seedvc_chunk_workers"] = chunk_workers
        seedvc_result = None
        if chunk_seconds:
            metrics["seedvc_chunked_attempted"] = True
            try:
                update(f"分段换声（{chunk_seconds}秒 / {chunk_workers}路）", 70)
                seedvc_result = _convert_seedvc_chunked(
                    options=options,
                    preset=preset,
                    source_vocal=source_vocal,
                    prepared_voice=prepared_voice,
                    converted_dir=converted_dir,
                    actual_device=actual_device,
                    chunk_seconds=chunk_seconds,
                    workers=chunk_workers,
                )
                metrics["seedvc_chunked_used"] = True
            except Exception as exc:
                metrics["seedvc_chunk_error"] = str(exc)
                update("分段换声失败，回退整段换声", 70)

        if seedvc_result is None:
            seedvc_result = _convert_seedvc_whole(
                options=options,
                preset=preset,
                source_vocal=source_vocal,
                prepared_voice=prepared_voice,
                converted_dir=converted_dir,
                actual_device=actual_device,
                allow_cpu_fallback=allow_cpu_fallback,
            )
        converted_vocal = seedvc_result.output
        metrics["seedvc_cache_hit"] = seedvc_result.cache_hit
        metrics["seedvc_seconds"] = seedvc_result.elapsed_seconds
        metrics["seedvc_device"] = seedvc_result.device_used
        metrics["mps_used"] = seedvc_result.device_used == "mps"
        metrics["seedvc_cpu_fallback_used"] = seedvc_result.cpu_fallback_used
        metrics["convert_seconds"] = seedvc_result.elapsed_seconds
    elif engine.requires_training:
        if not voice_profile:
            raise ValueError(f"{engine.name} 需要选择一个已保存音色")
        if options.voice_model_id:
            voice_model = get_voice_model_by_id(
                options.voice_model_id,
                voice_id=voice_profile.id,
                engine_id=options.engine_id,
                db_path=options.library_db_path,
            )
            if voice_model.status != "ready":
                raise FileNotFoundError(f"选择的 {engine.name} 模型还没有准备好。")
        else:
            voice_model = get_voice_model(voice_profile.id, engine_id=options.engine_id, db_path=options.library_db_path)
        if not voice_model:
            raise FileNotFoundError(f"{engine.name} 模型不存在，请先准备数据并训练。")
        metrics["voice_model_id"] = voice_model.id
        if not engine.is_available():
            missing = ", ".join(str(item) for item in engine_check.get("missing", []))
            raise RuntimeError(f"{engine.name} 未安装或未配置：{missing}")
        metrics["trained_model_path"] = voice_model.model_path
        metrics["trained_model_dataset_seconds"] = voice_model.dataset_seconds
        metrics["trained_model_index_path"] = voice_model.index_path
        metrics["trained_model_status"] = voice_model.status
        if options.engine_id == "rvc_mlx":
            metrics["rvc_mlx_model_path"] = voice_model.model_path
            metrics["rvc_mlx_dataset_seconds"] = voice_model.dataset_seconds
            metrics["rvc_mlx_index_path"] = voice_model.index_path
            metrics["rvc_mlx_status"] = voice_model.status
        rvc_convert_options = {
            "cache_dir": options.cache_dir,
            "index_path": voice_model.index_path,
            "voice_model_id": voice_model.id,
            "index_rate": effective_rvc_index_rate,
            "protect": rvc_preset.protect,
            "pitch_shift": rvc_preset.pitch,
            "f0_method": rvc_preset.f0_method,
            "clean_audio": rvc_preset.clean_audio,
        }
        engine_result = engine.convert(
            source_vocal=conversion_source_vocal,
            target_voice_or_model=Path(voice_model.model_path),
            output_dir=converted_dir / options.engine_id,
            options=rvc_convert_options,
        )
        converted_vocal = engine_result.converted_vocal_path
        metrics["rvc_index_rate"] = engine_result.metadata.get("index_rate", effective_rvc_index_rate)
        metrics["applio_index_fallback_used"] = bool(engine_result.metadata.get("index_fallback_used"))
        metrics["applio_crashed"] = bool(engine_result.metadata.get("crashed"))
        metrics["applio_crash_signal"] = engine_result.metadata.get("crash_signal")
        metrics["trained_model_cache_hit"] = engine_result.cache_hit
        if options.engine_id == "rvc_mlx":
            metrics["rvc_mlx_cache_hit"] = engine_result.cache_hit
        metrics["convert_seconds"] = engine_result.seconds
        metrics["seedvc_device"] = engine_result.device
        metrics["mps_used"] = engine_result.device == "mps"
    else:
        raise ValueError(f"Unsupported conversion engine: {options.engine_id}")
    return ConversionStageResult(
        converted_vocal=converted_vocal,
        voice_model=voice_model if "voice_model" in locals() else None,
        rvc_convert_options=rvc_convert_options if "rvc_convert_options" in locals() else None,
    )
