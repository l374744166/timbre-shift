"""Seed-VC conversion helpers for the main pipeline."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .audio import concat_audio_files, probe_duration, split_audio_fixed
from .pipeline_config import PipelineOptions, RenderPreset
from .seed_vc import SeedVCResult, convert_singing_voice_result


def _convert_seedvc_whole(
    options: PipelineOptions,
    preset: RenderPreset,
    source_vocal: Path,
    prepared_voice: Path,
    converted_dir: Path,
    actual_device: str,
    allow_cpu_fallback: bool,
) -> SeedVCResult:
    return convert_singing_voice_result(
        seed_vc_dir=options.seed_vc_dir,
        source_vocal=source_vocal,
        target_voice=prepared_voice,
        output_dir=converted_dir,
        diffusion_steps=preset.diffusion_steps,
        length_adjust=options.length_adjust,
        inference_cfg_rate=preset.inference_cfg_rate,
        semi_tone_shift=options.semi_tone_shift,
        fp16=options.fp16 if options.fp16 is not None else False,
        device=actual_device,
        target_voice_seconds=preset.reference_seconds,
        cache_dir=options.cache_dir,
        allow_cpu_fallback=allow_cpu_fallback,
    )


def _convert_seedvc_chunked(
    options: PipelineOptions,
    preset: RenderPreset,
    source_vocal: Path,
    prepared_voice: Path,
    converted_dir: Path,
    actual_device: str,
    chunk_seconds: int,
    workers: int,
) -> SeedVCResult:
    duration = probe_duration(source_vocal) or 0
    if duration <= chunk_seconds * 1.25:
        raise ValueError("Audio is too short for chunked Seed-VC conversion")

    chunk_dir = converted_dir / f"chunks_{chunk_seconds}s"
    input_dir = chunk_dir / "input"
    output_root = chunk_dir / "output"
    chunks = split_audio_fixed(source_vocal, input_dir, chunk_seconds)
    if len(chunks) < 2:
        raise ValueError("Seed-VC chunking produced fewer than two chunks")

    worker_count = min(max(1, workers), len(chunks))
    results: list[SeedVCResult | None] = [None] * len(chunks)

    def convert_one(index: int, chunk: Path) -> tuple[int, SeedVCResult]:
        result = convert_singing_voice_result(
            seed_vc_dir=options.seed_vc_dir,
            source_vocal=chunk,
            target_voice=prepared_voice,
            output_dir=output_root / f"chunk_{index:04d}",
            diffusion_steps=preset.diffusion_steps,
            length_adjust=options.length_adjust,
            inference_cfg_rate=preset.inference_cfg_rate,
            semi_tone_shift=options.semi_tone_shift,
            fp16=options.fp16 if options.fp16 is not None else False,
            device=actual_device,
            target_voice_seconds=preset.reference_seconds,
            cache_dir=options.cache_dir,
            allow_cpu_fallback=False,
        )
        return index, result

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(convert_one, index, chunk) for index, chunk in enumerate(chunks)]
        for future in as_completed(futures):
            index, result = future.result()
            results[index] = result

    ordered = [result for result in results if result is not None]
    if len(ordered) != len(chunks):
        raise RuntimeError("Seed-VC chunked conversion did not finish all chunks")

    output = concat_audio_files(
        [result.output for result in ordered],
        converted_dir / f"converted_chunked_{chunk_seconds}s.wav",
    )
    elapsed = time.perf_counter() - start
    return SeedVCResult(
        output=output,
        cache_hit=all(result.cache_hit for result in ordered),
        elapsed_seconds=elapsed,
        cache_key="chunked-" + "-".join(result.cache_key[:8] for result in ordered),
        device_requested=actual_device,
        device_used=actual_device,
        cpu_fallback_used=False,
    )
