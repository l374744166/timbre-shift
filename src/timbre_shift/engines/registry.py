"""Registry for conversion engines."""

from __future__ import annotations

from .base import ConversionEngine
from .rvc_mlx_engine import RVCMLXEngine
from .seedvc_engine import SeedVCEngine


_ENGINES: dict[str, ConversionEngine] = {
    SeedVCEngine.id: SeedVCEngine(),
    RVCMLXEngine.id: RVCMLXEngine(),
}


def list_engines() -> list[ConversionEngine]:
    return list(_ENGINES.values())


def get_engine(engine_id: str) -> ConversionEngine:
    try:
        return _ENGINES[engine_id]
    except KeyError as exc:
        available = ", ".join(sorted(_ENGINES))
        raise ValueError(f"Unknown conversion engine: {engine_id}. Available: {available}") from exc
