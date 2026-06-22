"""Conversion engine abstractions and registry."""

from .base import ConversionEngine, EngineResult


def get_engine(engine_id: str):
    from .registry import get_engine as _get_engine

    return _get_engine(engine_id)


def list_engines():
    from .registry import list_engines as _list_engines

    return _list_engines()

__all__ = ["ConversionEngine", "EngineResult", "get_engine", "list_engines"]
