from __future__ import annotations

from email.message import Message
from io import BytesIO
from pathlib import Path

from timbre_shift.web_uploads import read_form_fields, read_voice_library_upload


def multipart_body(boundary: str, parts: list[tuple[str, str | None, bytes]]) -> bytes:
    chunks: list[bytes] = []
    for name, filename, payload in parts:
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        disposition = f'Content-Disposition: form-data; name="{name}"'
        if filename:
            disposition += f'; filename="{filename}"'
        chunks.append(f"{disposition}\r\n\r\n".encode("utf-8"))
        chunks.append(payload)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks)


def headers_for(boundary: str, body: bytes) -> Message:
    headers = Message()
    headers["content-type"] = f"multipart/form-data; boundary={boundary}"
    headers["content-length"] = str(len(body))
    return headers


def test_read_form_fields_without_cgi():
    boundary = "timbre-test-boundary"
    body = multipart_body(boundary, [("voice_profile_id", None, "毛不易".encode("utf-8"))])

    fields = read_form_fields(BytesIO(body), headers_for(boundary, body))

    assert fields["voice_profile_id"] == "毛不易"


def test_read_voice_library_upload_saves_file(tmp_path: Path):
    boundary = "timbre-upload-boundary"
    body = multipart_body(
        boundary,
        [
            ("voice_name", None, "测试音色".encode("utf-8")),
            ("voice_source_type", None, b"mixed_voice"),
            ("voice", "demo vocal.wav", b"audio-bytes"),
        ],
    )

    paths, voice_name, source_type = read_voice_library_upload(
        BytesIO(body),
        headers_for(boundary, body),
        tmp_path,
    )

    assert voice_name == "测试音色"
    assert source_type == "mixed_voice"
    assert len(paths) == 1
    assert paths[0].read_bytes() == b"audio-bytes"


def test_rvc_index_rate_enables_memory_without_extra_checkbox(tmp_path: Path):
    from timbre_shift.web_uploads import read_uploads

    boundary = "timbre-generate-boundary"
    body = multipart_body(
        boundary,
        [
            ("engine_id", None, b"rvc_applio"),
            ("voice_profile_id", None, b"voice-1"),
            ("song_id", None, b"song-1"),
            ("rvc_index_rate", None, b"0.25"),
            ("voice", "voice.wav", b"voice"),
            ("song", "song.wav", b"song"),
        ],
    )

    _files, fields = read_uploads(BytesIO(body), headers_for(boundary, body), tmp_path)

    assert fields["rvc_index_rate"] == "0.25"
    assert fields["allow_experimental_index"] is True
