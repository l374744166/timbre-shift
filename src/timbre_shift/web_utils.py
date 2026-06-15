"""Small helpers used by the local web server."""

from __future__ import annotations

import re
from pathlib import Path


def safe_filename(name: str) -> str:
    path_name = Path(name).name
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", Path(path_name).stem).strip("-")
    suffix = re.sub(r"[^A-Za-z0-9.]+", "", Path(path_name).suffix)
    return f"{stem or 'upload'}{suffix or '.wav'}"


def safe_download_filename(name: str | None, fallback: str) -> str:
    fallback_path = Path(fallback)
    fallback_suffix = fallback_path.suffix or ".mp3"
    raw_name = (name or fallback_path.name).strip()
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "-", raw_name)
    cleaned = re.sub(r"\s+", " ", Path(cleaned).name).strip(" .")
    if not cleaned:
        cleaned = fallback_path.name
    if not Path(cleaned).suffix:
        cleaned = f"{cleaned}{fallback_suffix}"
    return cleaned

