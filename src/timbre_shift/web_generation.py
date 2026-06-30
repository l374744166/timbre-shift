"""Song generation request handling for the web API."""

from __future__ import annotations

from pathlib import Path

from .library import DEFAULT_DB_PATH, DEFAULT_LIBRARY_DIR, list_voice_models, list_voice_samples
from .pipeline import PipelineOptions, check_environment, run_demo
from .web_results import build_generation_response, create_test_result, read_metrics_payload
from .web_state import PROGRESS


def generate_song_payload(
    *,
    seed_vc_dir: Path,
    files: dict[str, Path],
    fields: dict[str, object],
    root: Path,
    output_dir: Path,
) -> dict[str, object]:
    mode = str(fields["mode"])
    engine_id = str(fields["engine_id"])
    skip_separation = bool(fields["skip_separation"])
    voice_id = str(fields["voice_profile_id"])

    _validate_generation_selection(engine_id, voice_id, str(fields["voice_model_id"]))
    PROGRESS.update("检查运行环境", 3)
    report = check_environment(seed_vc_dir)
    if not report.ready:
        PROGRESS.update("生成测试结果", 50)
        test_output = create_test_result(output_dir / "test-result.wav")
        PROGRESS.update("测试生成完成", 100, "completed")
        return {
            "download_url": f"/download/{test_output.name}",
            "filename": test_output.name,
            "mode": "test",
            "message": "测试生成完成；真实换声还缺少 ffmpeg、Demucs 或 Seed-VC",
            "missing": report.missing,
        }

    final_mix = run_demo(
        PipelineOptions(
            voice=files.get("voice"),
            song=files.get("song"),
            seed_vc_dir=seed_vc_dir,
            work_dir=root / "data" / "processed" / "web",
            output_dir=output_dir,
            cache_dir=root / "data" / "cache",
            library_dir=DEFAULT_LIBRARY_DIR,
            library_db_path=DEFAULT_DB_PATH,
            render_mode=mode,
            engine_id=engine_id,
            voice_model_id=str(fields["voice_model_id"]) or None,
            device="mps",
            skip_separation=skip_separation,
            voice_profile_id=str(fields["voice_profile_id"]) or None,
            song_id=str(fields["song_id"]) or None,
            save_voice_to_library=bool(fields["save_voice"]),
            save_song_to_library=bool(fields["save_song"]),
            voice_name=str(fields["voice_name"]) or None,
            song_title=str(fields["song_title"]) or None,
            rights_confirmed=bool(fields["rights_confirmed"]),
            source_mode="clean_vocal" if skip_separation else "full_song",
            rvc_preset=str(fields["rvc_preset"]),
            diction_mode=str(fields["diction_mode"]),
            vocal_style=str(fields["vocal_style"]),
            allow_experimental_index=bool(fields["allow_experimental_index"]),
            rvc_index_rate=float(fields["rvc_index_rate"]) if fields["rvc_index_rate"] != "" else None,
            generate_variants=bool(fields["generate_variants"]),
            pre_rvc_cleanup_mode=str(fields["pre_rvc_cleanup_mode"]),
            source_vocal_quality_enabled=bool(fields.get("source_vocal_quality_enabled", True)),
            deharsh_mode=str(fields.get("deharsh_mode", "off")),
            mix_style=str(fields["mix_style"]),
            separation_mode=str(fields.get("separation_mode", "standard")),
        ),
        progress=lambda step, percent: PROGRESS.update(step, percent),
    )
    PROGRESS.update("生成完成", 100, "completed")
    return build_generation_response(
        output_dir,
        final_mix,
        read_metrics_payload(output_dir / "metrics.json"),
        render_mode=mode,
        engine_id=engine_id,
        fields=fields,
    )


def _validate_generation_selection(engine_id: str, voice_id: str, selected_model_id: str) -> None:
    if engine_id == "seedvc" and voice_id and not list_voice_samples(voice_id, db_path=DEFAULT_DB_PATH):
        raise ValueError("这个音色库还没有素材，不能用于 Seed-VC 生成")
    if engine_id in {"rvc_applio", "rvc_mlx"}:
        ready_models = list_voice_models(voice_id, engine_id=engine_id, db_path=DEFAULT_DB_PATH)
        ready_models = [model for model in ready_models if model.status == "ready"]
        if not selected_model_id and not ready_models:
            raise ValueError("Applio RVC 还没有可用模型，请先训练模型再生成")
