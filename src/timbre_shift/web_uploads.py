"""Upload and multipart form parsing helpers for the local web UI."""

from __future__ import annotations

import time
from dataclasses import dataclass
from email.message import Message
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from typing import BinaryIO

from .pipeline import PRESETS
from .web_utils import safe_filename


SUPPORTED_ENGINES = {"seedvc", "rvc_applio", "rvc_mlx"}


@dataclass(frozen=True)
class UploadedPart:
    name: str
    filename: str
    data: bytes


class MultipartForm:
    def __init__(self, fields: dict[str, list[str]], files: dict[str, list[UploadedPart]]) -> None:
        self._fields = fields
        self._files = files

    def keys(self) -> list[str]:
        return list(self._fields.keys()) + [key for key in self._files if key not in self._fields]

    def getfirst(self, key: str, default_value: str = "") -> str:
        values = self._fields.get(key)
        return values[0] if values else default_value

    def files(self, key: str) -> list[UploadedPart]:
        return self._files.get(key, [])


def read_uploads(
    rfile: BinaryIO,
    headers: Message,
    upload_root: Path,
) -> tuple[dict[str, Path], dict[str, object]]:
    form = _read_multipart_form(rfile, headers, "请上传音频文件")
    target_dir = _timestamped_upload_dir(upload_root)

    saved: dict[str, Path] = {}
    for field in ["voice", "song"]:
        items = _upload_items(form, field)
        if not items:
            continue
        item = items[0]
        path = target_dir / f"{field}-{safe_filename(item.filename)}"
        _write_upload(item, path)
        saved[field] = path

    mode = form.getfirst("mode", "m2max_hq_30")
    if mode not in PRESETS:
        mode = "m2max_hq_30"

    engine_id = form.getfirst("engine_id", "seedvc")
    if engine_id not in SUPPORTED_ENGINES:
        engine_id = "seedvc"

    fields: dict[str, object] = {
        "mode": mode,
        "engine_id": engine_id,
        "voice_model_id": form.getfirst("voice_model_id", ""),
        "skip_separation": False,
        "voice_profile_id": form.getfirst("voice_profile_id", ""),
        "song_id": form.getfirst("song_id", ""),
        "save_voice": False,
        "save_song": False,
        "voice_name": form.getfirst("voice_name", ""),
        "song_title": form.getfirst("song_title", ""),
        "rights_confirmed": True,
        "rvc_preset": form.getfirst("rvc_preset", "stable_balanced"),
        "diction_mode": form.getfirst("diction_mode", "light"),
        "vocal_style": form.getfirst("vocal_style", "neutral"),
        "allow_experimental_index": form.getfirst("allow_experimental_index", "") == "on",
        "rvc_index_rate": form.getfirst("rvc_index_rate", ""),
        "generate_variants": form.getfirst("generate_variants", "") == "on",
        "pre_rvc_cleanup_mode": form.getfirst("pre_rvc_cleanup_mode", "off"),
        "source_vocal_quality_enabled": form.getfirst("source_vocal_quality_enabled", "on") == "on",
        "deharsh_mode": form.getfirst("deharsh_mode", "off"),
        "mix_style": form.getfirst("mix_style", "natural"),
    }
    if not fields["voice_profile_id"] and "voice" not in saved:
        raise ValueError("请选择本地音色，或上传一个新声音样本")
    if not fields["song_id"] and "song" not in saved:
        raise ValueError("请选择本地歌曲，或上传一个新歌曲文件")
    return saved, fields


def read_form_fields(rfile: BinaryIO, headers: Message) -> dict[str, object]:
    form = _read_multipart_form(rfile, headers, "表单格式不正确")
    return {key: form.getfirst(key, "") for key in form.keys()}


def read_voice_library_upload(
    rfile: BinaryIO,
    headers: Message,
    upload_root: Path,
) -> tuple[list[Path], str, str]:
    form = _read_multipart_form(rfile, headers, "请上传声音样本")
    items = _upload_items(form, "voice")
    if not items:
        raise ValueError("先选择一个或多个声音样本")

    paths = _save_upload_items(items, _timestamped_upload_dir(upload_root), "voice-library")
    raw_name = str(form.getfirst("voice_name", "")).strip()
    voice_name = raw_name or Path(safe_filename(items[0].filename)).stem or "我的声音"
    voice_source_type = _clean_voice_source_type(str(form.getfirst("voice_source_type", "clean_voice")))
    return paths, voice_name, voice_source_type


def read_voice_sample_upload(
    rfile: BinaryIO,
    headers: Message,
    upload_root: Path,
) -> tuple[list[Path], str, str, str]:
    form = _read_multipart_form(rfile, headers, "请上传声音素材")
    items = _upload_items(form, "voice")
    if not items:
        raise ValueError("先选择一个或多个声音素材")

    paths = _save_upload_items(items, _timestamped_upload_dir(upload_root), "voice-sample")
    raw_name = str(form.getfirst("voice_name", "")).strip()
    voice_name = raw_name or Path(safe_filename(items[0].filename)).stem or "声音素材"
    voice_source_type = _clean_voice_source_type(str(form.getfirst("voice_source_type", "clean_voice")))
    voice_profile_id = str(form.getfirst("voice_profile_id", "")).strip()
    return paths, voice_name, voice_source_type, voice_profile_id


def _read_multipart_form(rfile: BinaryIO, headers: Message, error_message: str) -> MultipartForm:
    content_type = headers.get("content-type", "")
    if not content_type.startswith("multipart/form-data"):
        raise ValueError(error_message)
    try:
        content_length = int(headers.get("content-length", "0") or "0")
    except ValueError as exc:
        raise ValueError("上传内容长度不正确") from exc
    if content_length <= 0:
        raise ValueError(error_message)

    body = rfile.read(content_length)
    message = BytesParser(policy=default).parsebytes(
        (
            f"Content-Type: {content_type}\r\n"
            "MIME-Version: 1.0\r\n"
            "\r\n"
        ).encode("utf-8")
        + body
    )
    fields: dict[str, list[str]] = {}
    files: dict[str, list[UploadedPart]] = {}
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            files.setdefault(name, []).append(UploadedPart(name=name, filename=filename, data=payload))
        else:
            charset = part.get_content_charset() or "utf-8"
            fields.setdefault(name, []).append(payload.decode(charset, errors="replace"))
    return MultipartForm(fields, files)


def _timestamped_upload_dir(upload_root: Path) -> Path:
    target_dir = upload_root / str(int(time.time()))
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def _upload_items(form: MultipartForm, field: str) -> list[UploadedPart]:
    return [item for item in form.files(field) if item.filename]


def _save_upload_items(items: list[UploadedPart], target_dir: Path, prefix: str) -> list[Path]:
    paths: list[Path] = []
    for index, item in enumerate(items, start=1):
        path = target_dir / f"{prefix}-{index}-{safe_filename(item.filename)}"
        _write_upload(item, path)
        paths.append(path)
    return paths


def _write_upload(item: UploadedPart, path: Path) -> None:
    with path.open("wb") as output:
        output.write(item.data)


def _clean_voice_source_type(value: str) -> str:
    if value not in {"clean_voice", "mixed_voice"}:
        return "clean_voice"
    return value
