"""Seed-VC conversion engine wrapper."""

from __future__ import annotations

from pathlib import Path

from .base import EngineResult
from ..seed_vc import convert_singing_voice_result


class SeedVCEngine:
    id = "seedvc"
    name = "Seed-VC"
    requires_training = False

    def is_available(self) -> bool:
        return True

    def check(self) -> dict[str, object]:
        return {
            "engine_id": self.id,
            "engine_name": self.name,
            "available": True,
            "requires_training": self.requires_training,
            "missing": [],
        }

    def convert(
        self,
        source_vocal: Path,
        target_voice_or_model: Path,
        output_dir: Path,
        options: dict[str, object],
    ) -> EngineResult:
        result = convert_singing_voice_result(
            seed_vc_dir=Path(options["seed_vc_dir"]),
            source_vocal=source_vocal,
            target_voice=target_voice_or_model,
            output_dir=output_dir,
            diffusion_steps=int(options.get("diffusion_steps", 10)),
            length_adjust=float(options.get("length_adjust", 1.0)),
            inference_cfg_rate=float(options.get("inference_cfg_rate", 0.0)),
            semi_tone_shift=int(options.get("semi_tone_shift", 0)),
            fp16=bool(options.get("fp16", False)),
            device=str(options.get("device", "mps")),
            target_voice_seconds=int(options.get("target_voice_seconds", 16)),
            cache_dir=Path(options["cache_dir"]) if options.get("cache_dir") else None,
            allow_cpu_fallback=bool(options.get("allow_cpu_fallback", False)),
        )
        return EngineResult(
            converted_vocal_path=result.output,
            engine_id=self.id,
            engine_name=self.name,
            seconds=result.elapsed_seconds,
            device=result.device_used,
            cache_hit=result.cache_hit,
            metadata={
                "cache_key": result.cache_key,
                "device_requested": result.device_requested,
                "cpu_fallback_used": result.cpu_fallback_used,
            },
        )
