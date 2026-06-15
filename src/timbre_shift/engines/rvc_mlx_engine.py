"""Experimental RVC-MLX conversion engine wrapper."""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import sys
from pathlib import Path

from .base import EngineResult
from ..rvc_mlx import convert_with_rvc_mlx


class RVCMLXEngine:
    id = "rvc_mlx"
    name = "RVC-MLX Experimental"
    requires_training = True

    def is_available(self) -> bool:
        return bool(self.check()["available"])

    def check(self) -> dict[str, object]:
        missing: list[str] = []
        mlx_available = importlib.util.find_spec("mlx") is not None
        if not mlx_available:
            missing.append("mlx")

        executable = os.environ.get("RVC_MLX_COMMAND") or shutil.which("rvc-mlx")
        repo = os.environ.get("RVC_MLX_REPO")
        if not executable and not repo:
            missing.append("RVC_MLX_COMMAND or RVC_MLX_REPO")

        return {
            "engine_id": self.id,
            "engine_name": self.name,
            "available": not missing,
            "requires_training": self.requires_training,
            "missing": missing,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "mlx_import": mlx_available,
            "rvc_mlx_command": executable,
            "rvc_mlx_repo": repo,
            "install_hint": (
                "Install MLX and configure an RVC-MLX implementation, then set "
                "RVC_MLX_COMMAND or RVC_MLX_REPO. The wrapper is intentionally "
                "experimental so Seed-VC remains the stable default."
            ),
        }

    def convert(
        self,
        source_vocal: Path,
        target_voice_or_model: Path,
        output_dir: Path,
        options: dict[str, object],
    ) -> EngineResult:
        return convert_with_rvc_mlx(
            source_vocal=source_vocal,
            model_path=target_voice_or_model,
            output_dir=output_dir,
            options=options,
            engine_id=self.id,
            engine_name=self.name,
        )
