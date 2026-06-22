"""Static asset loading for the local web UI."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


ASSET_DIR = Path(__file__).with_name("web_static")


@lru_cache(maxsize=None)
def load_asset(name: str) -> str:
    return (ASSET_DIR / name).read_text(encoding="utf-8")


def style_css() -> str:
    return load_asset("styles.css")


def app_javascript() -> str:
    return load_asset("app.js")
