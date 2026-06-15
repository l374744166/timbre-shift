"""Applio RVC conversion engine wrapper."""

from __future__ import annotations

import platform
import sys
from pathlib import Path

from .base import EngineResult
from ..rvc_applio import APPLIO_ENGINE_NAME, check_applio, convert_with_applio


class RVCApplioEngine:
    id = "rvc_applio"
    name = APPLIO_ENGINE_NAME
    requires_training = True

    def is_available(self) -> bool:
        return bool(self.check()["available"])

    def check(self) -> dict[str, object]:
        check = check_applio()
        return {
            "engine_id": self.id,
            "engine_name": self.name,
            "available": check.available,
            "requires_training": self.requires_training,
            "missing": check.missing,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "applio_dir": str(check.applio_dir),
            "applio_python": str(check.python) if check.python else None,
            "install_hint": "在 vendor/applio 运行 ./run-install.sh，或设置 APPLIO_DIR / APPLIO_PYTHON。",
        }

    def convert(
        self,
        source_vocal: Path,
        target_voice_or_model: Path,
        output_dir: Path,
        options: dict[str, object],
    ) -> EngineResult:
        return convert_with_applio(
            source_vocal=source_vocal,
            model_path=target_voice_or_model,
            output_dir=output_dir,
            options=options,
            engine_id=self.id,
            engine_name=self.name,
        )
