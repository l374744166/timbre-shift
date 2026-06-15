"""Base types for vocal conversion engines."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class EngineResult:
    converted_vocal_path: Path
    engine_id: str
    engine_name: str
    seconds: float
    device: str | None
    cache_hit: bool
    metadata: dict[str, object] = field(default_factory=dict)


class ConversionEngine(Protocol):
    id: str
    name: str
    requires_training: bool

    def is_available(self) -> bool:
        ...

    def check(self) -> dict[str, object]:
        ...

    def convert(
        self,
        source_vocal: Path,
        target_voice_or_model: Path,
        output_dir: Path,
        options: dict[str, object],
    ) -> EngineResult:
        ...
