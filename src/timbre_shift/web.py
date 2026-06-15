"""Tiny local web UI for the first Timbre Shift demo."""

from __future__ import annotations

import cgi
import json
import math
import mimetypes
import time
import wave
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Tuple
from urllib.parse import parse_qs, quote, urlparse

from .demucs import separate_vocals
from .library import (
    DEFAULT_DB_PATH,
    DEFAULT_LIBRARY_DIR,
    add_voice_sample_to_profile,
    archive_voice_profile,
    list_voice_samples,
    save_voice_to_library,
)
from .pipeline import PRESETS, PipelineOptions, check_environment, run_demo
from .vocal_segments import compact_for_conversion
from .web_state import PROGRESS
from .web_template import page_html
from .web_utils import safe_download_filename, safe_filename


ROOT = Path.cwd()
UPLOAD_ROOT = ROOT / "data" / "raw" / "web_uploads"
OUTPUT_DIR = ROOT / "outputs" / "web"
class AppHandler(BaseHTTPRequestHandler):
    seed_vc_dir: Path = Path("vendor/seed-vc")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        request_path = parsed.path
        if request_path == "/":
            self.send_html(page_html())
            return
        if request_path == "/api/check":
            report = check_environment(self.seed_vc_dir)
            self.send_json({"ready": report.ready, "missing": report.missing, "text": report.to_text()})
            return
        if request_path == "/api/progress":
            self.send_json(PROGRESS.snapshot())
            return
        if request_path.startswith("/download/"):
            download_name = parse_qs(parsed.query).get("name", [None])[0]
            self.send_file(
                OUTPUT_DIR / safe_filename(request_path.removeprefix("/download/")),
                download_name=download_name,
            )
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        request_path = parsed.path
        if request_path.startswith("/download/"):
            download_name = parse_qs(parsed.query).get("name", [None])[0]
            self.send_file(
                OUTPUT_DIR / safe_filename(request_path.removeprefix("/download/")),
                head_only=True,
                download_name=download_name,
            )
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path == "/api/add-voice-sample":
            try:
                voice_uploads, voice_name, voice_source_type, voice_profile_id = self.read_voice_sample_upload()
                if not voice_profile_id:
                    raise ValueError("先选择一个已保存音色")
                sample = None
                for index, voice_path in enumerate(voice_uploads, start=1):
                    source_type = "upload_voice"
                    clean_path = voice_path
                    if voice_source_type == "mixed_voice":
                        PROGRESS.reset(f"高质量分离素材人声 {index}/{len(voice_uploads)}", 5, "running")
                        separated = separate_vocals(
                            voice_path,
                            output_dir=ROOT / "data" / "processed" / "web" / "voice_samples",
                            model="htdemucs_ft",
                            cache_dir=ROOT / "data" / "cache",
                            overlap=0.25,
                            shifts=0,
                        )
                        clean_path = separated.vocals
                        source_type = "separated_compact_voice"
                        try:
                            PROGRESS.update(f"筛选有效素材人声片段 {index}/{len(voice_uploads)}", 70)
                            compact = compact_for_conversion(
                                separated.vocals,
                                clean_path.parent / f"compact_voice_{index}.wav",
                            )
                            clean_path = compact.audio
                        except ValueError:
                            source_type = "separated_voice"
                    PROGRESS.update(f"添加素材并刷新参考音频 {index}/{len(voice_uploads)}", 85)
                    sample = add_voice_sample_to_profile(
                        voice_id=voice_profile_id,
                        input_audio=voice_path,
                        clean_audio=clean_path,
                        name=voice_name if len(voice_uploads) == 1 else f"{voice_name} {index}",
                        source_type=source_type,
                        library_dir=DEFAULT_LIBRARY_DIR,
                        db_path=DEFAULT_DB_PATH,
                    )
                sample_count = len(list_voice_samples(voice_profile_id, db_path=DEFAULT_DB_PATH))
                PROGRESS.update("素材已添加", 100, "completed")
                self.send_json(
                    {
                        "id": sample.id if sample else None,
                        "voice_profile_id": voice_profile_id,
                        "sample_count": sample_count,
                        "added_count": len(voice_uploads),
                        "quality_score": sample.quality_score if sample else None,
                        "noise_score": sample.noise_score if sample else None,
                        "message": "素材已添加",
                    }
                )
            except Exception as exc:
                PROGRESS.fail(str(exc))
                self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        if self.path == "/api/delete-voice":
            try:
                fields = self.read_form_fields()
                voice_id = str(fields.get("voice_profile_id", "")).strip()
                if not voice_id:
                    raise ValueError("请选择要删除的音色")
                archive_voice_profile(voice_id, db_path=DEFAULT_DB_PATH)
                self.send_json({"id": voice_id, "message": "音色已删除"})
            except Exception as exc:
                PROGRESS.fail(str(exc))
                self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        if self.path == "/api/save-voice":
            try:
                voice_uploads, voice_name, voice_source_type = self.read_voice_library_upload()
                prepared_uploads: list[tuple[Path, Path, str]] = []
                for index, voice_path in enumerate(voice_uploads, start=1):
                    source_type = "upload_voice"
                    clean_path = voice_path
                    if voice_source_type == "mixed_voice":
                        PROGRESS.reset(f"高质量分离音色人声 {index}/{len(voice_uploads)}", 5, "running")
                        separated = separate_vocals(
                            voice_path,
                            output_dir=ROOT / "data" / "processed" / "web" / "voice_separated",
                            model="htdemucs_ft",
                            cache_dir=ROOT / "data" / "cache",
                            overlap=0.25,
                            shifts=0,
                        )
                        clean_path = separated.vocals
                        source_type = "separated_compact_voice"
                        try:
                            PROGRESS.update(f"筛选有效音色人声片段 {index}/{len(voice_uploads)}", 70)
                            compact = compact_for_conversion(
                                separated.vocals,
                                clean_path.parent / f"compact_voice_{index}.wav",
                            )
                            clean_path = compact.audio
                        except ValueError:
                            source_type = "separated_voice"
                    prepared_uploads.append((voice_path, clean_path, source_type))
                PROGRESS.update("保存音色", 80)
                first_voice_path, first_clean_path, first_source_type = prepared_uploads[0]
                profile = save_voice_to_library(
                    input_audio=first_voice_path,
                    clean_audio=first_clean_path,
                    name=voice_name,
                    description=None,
                    source_type=first_source_type,
                    rights_status="own_voice",
                    allowed_as_target=True,
                    library_dir=DEFAULT_LIBRARY_DIR,
                    db_path=DEFAULT_DB_PATH,
                )
                for index, (extra_voice_path, extra_clean_path, extra_source_type) in enumerate(prepared_uploads[1:], start=2):
                    percent = min(98, 80 + int(index / len(prepared_uploads) * 15))
                    PROGRESS.update(f"追加音色素材 {index}/{len(prepared_uploads)}", percent)
                    add_voice_sample_to_profile(
                        voice_id=profile.id,
                        input_audio=extra_voice_path,
                        clean_audio=extra_clean_path,
                        name=f"{voice_name} {index}",
                        source_type=extra_source_type,
                        library_dir=DEFAULT_LIBRARY_DIR,
                        db_path=DEFAULT_DB_PATH,
                    )
                sample_count = len(list_voice_samples(profile.id, db_path=DEFAULT_DB_PATH))
                PROGRESS.update("音色已保存", 100, "completed")
                self.send_json(
                    {
                        "id": profile.id,
                        "name": profile.name,
                        "source_type": first_source_type,
                        "sample_count": sample_count,
                        "added_count": len(prepared_uploads),
                        "message": "音色已保存",
                    }
                )
            except Exception as exc:
                PROGRESS.fail(str(exc))
                self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        if self.path != "/api/generate":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            PROGRESS.reset("接收上传文件", 1, "running")
            files, fields = self.read_uploads()
            mode = str(fields["mode"])
            skip_separation = bool(fields["skip_separation"])
            PROGRESS.update("检查运行环境", 3)
            report = check_environment(self.seed_vc_dir)
            if report.ready:
                final_mix = run_demo(
                    PipelineOptions(
                        voice=files.get("voice"),
                        song=files.get("song"),
                        seed_vc_dir=self.seed_vc_dir,
                        work_dir=ROOT / "data" / "processed" / "web",
                        output_dir=OUTPUT_DIR,
                        cache_dir=ROOT / "data" / "cache",
                        library_dir=DEFAULT_LIBRARY_DIR,
                        library_db_path=DEFAULT_DB_PATH,
                        render_mode=mode,
                        device="mps",
                        skip_separation=skip_separation,
                        voice_profile_id=str(fields["voice_profile_id"]) or None,
                        song_id=str(fields["song_id"]) or None,
                        save_voice_to_library=bool(fields["save_voice"]),
                        save_song_to_library=bool(fields["save_song"]),
                        voice_name=str(fields["voice_name"]) or None,
                        song_title=str(fields["song_title"]) or None,
                        rights_confirmed=bool(fields["rights_confirmed"]),
                        source_mode="clean_vocal" if skip_separation else "full_song",
                    ),
                    progress=lambda step, percent: PROGRESS.update(step, percent),
                )
                PROGRESS.update("生成完成", 100, "completed")
                message = f"{PRESETS[mode].name}生成完成"
                final_mp3 = OUTPUT_DIR / "final.mp3"
                metrics_path = OUTPUT_DIR / "metrics.json"
                metrics_payload = {}
                if metrics_path.exists():
                    metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
                self.send_json(
                    {
                        "download_url": f"/download/{final_mp3.name if final_mp3.exists() else final_mix.name}",
                        "download_mp3_url": f"/download/{final_mp3.name}" if final_mp3.exists() else None,
                        "download_wav_url": f"/download/{final_mix.name}",
                        "mp3_filename": final_mp3.name if final_mp3.exists() else None,
                        "wav_filename": final_mix.name,
                        "mode": "real",
                        "message": message,
                        "render_mode": mode,
                        "skip_separation": skip_separation,
                        "voice_profile_id": fields["voice_profile_id"],
                        "song_id": fields["song_id"],
                        "metrics": metrics_payload,
                    }
                )
            else:
                PROGRESS.update("生成测试结果", 50)
                test_output = create_test_result(OUTPUT_DIR / "test-result.wav")
                PROGRESS.update("测试生成完成", 100, "completed")
                self.send_json(
                    {
                        "download_url": f"/download/{test_output.name}",
                        "filename": test_output.name,
                        "mode": "test",
                        "message": "测试生成完成；真实换声还缺少 ffmpeg、Demucs 或 Seed-VC",
                        "missing": report.missing,
                    }
                )
        except BrokenPipeError as exc:
            if PROGRESS.snapshot().get("status") == "completed":
                return
            PROGRESS.fail(str(exc))
            write_error_metrics(OUTPUT_DIR / "metrics.json", str(exc))
        except Exception as exc:
            PROGRESS.fail(str(exc))
            write_error_metrics(OUTPUT_DIR / "metrics.json", str(exc))
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def read_uploads(self) -> Tuple[Dict[str, Path], Dict[str, object]]:
        content_type = self.headers.get("content-type", "")
        if not content_type.startswith("multipart/form-data"):
            raise ValueError("请上传音频文件")

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
            },
        )
        timestamp = str(int(time.time()))
        target_dir = UPLOAD_ROOT / timestamp
        target_dir.mkdir(parents=True, exist_ok=True)

        saved: Dict[str, Path] = {}
        for field in ["voice", "song"]:
            items = self._upload_items(form, field)
            if not items:
                continue
            item = items[0]
            filename = safe_filename(item.filename)
            path = target_dir / f"{field}-{filename}"
            with path.open("wb") as output:
                while True:
                    chunk = item.file.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
            saved[field] = path
        mode = form.getfirst("mode", "m2max_hq_30")
        if mode not in PRESETS:
            mode = "m2max_hq_30"
        skip_separation = False
        fields: Dict[str, object] = {
            "mode": mode,
            "skip_separation": skip_separation,
            "voice_profile_id": form.getfirst("voice_profile_id", ""),
            "song_id": form.getfirst("song_id", ""),
            "save_voice": False,
            "save_song": False,
            "voice_name": form.getfirst("voice_name", ""),
            "song_title": form.getfirst("song_title", ""),
            "rights_confirmed": True,
        }
        if not fields["voice_profile_id"] and "voice" not in saved:
            raise ValueError("请选择本地音色，或上传一个新声音样本")
        if not fields["song_id"] and "song" not in saved:
            raise ValueError("请选择本地歌曲，或上传一个新歌曲文件")
        return saved, fields

    def read_form_fields(self) -> Dict[str, object]:
        content_type = self.headers.get("content-type", "")
        if not content_type.startswith("multipart/form-data"):
            raise ValueError("表单格式不正确")
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
            },
        )
        return {key: form.getfirst(key, "") for key in form.keys()}

    def _upload_items(self, form: cgi.FieldStorage, field: str) -> list[cgi.FieldStorage]:
        raw_items = form[field] if field in form else []
        items = raw_items if isinstance(raw_items, list) else [raw_items]
        return [item for item in items if getattr(item, "filename", "")]

    def _save_upload_items(self, items: list[cgi.FieldStorage], target_dir: Path, prefix: str) -> list[Path]:
        paths: list[Path] = []
        for index, item in enumerate(items, start=1):
            filename = safe_filename(item.filename)
            path = target_dir / f"{prefix}-{index}-{filename}"
            with path.open("wb") as output:
                while True:
                    chunk = item.file.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
            paths.append(path)
        return paths

    def read_voice_library_upload(self) -> Tuple[list[Path], str, str]:
        content_type = self.headers.get("content-type", "")
        if not content_type.startswith("multipart/form-data"):
            raise ValueError("请上传声音样本")

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
            },
        )
        items = self._upload_items(form, "voice")
        if not items:
            raise ValueError("先选择一个或多个声音样本")

        timestamp = str(int(time.time()))
        target_dir = UPLOAD_ROOT / timestamp
        target_dir.mkdir(parents=True, exist_ok=True)
        paths = self._save_upload_items(items, target_dir, "voice-library")

        raw_name = str(form.getfirst("voice_name", "")).strip()
        voice_name = raw_name or Path(safe_filename(items[0].filename)).stem or "我的声音"
        voice_source_type = str(form.getfirst("voice_source_type", "clean_voice"))
        if voice_source_type not in {"clean_voice", "mixed_voice"}:
            voice_source_type = "clean_voice"
        return paths, voice_name, voice_source_type

    def read_voice_sample_upload(self) -> Tuple[list[Path], str, str, str]:
        content_type = self.headers.get("content-type", "")
        if not content_type.startswith("multipart/form-data"):
            raise ValueError("请上传声音素材")

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
            },
        )
        items = self._upload_items(form, "voice")
        if not items:
            raise ValueError("先选择一个或多个声音素材")

        timestamp = str(int(time.time()))
        target_dir = UPLOAD_ROOT / timestamp
        target_dir.mkdir(parents=True, exist_ok=True)
        paths = self._save_upload_items(items, target_dir, "voice-sample")

        raw_name = str(form.getfirst("voice_name", "")).strip()
        voice_name = raw_name or Path(safe_filename(items[0].filename)).stem or "声音素材"
        voice_source_type = str(form.getfirst("voice_source_type", "clean_voice"))
        if voice_source_type not in {"clean_voice", "mixed_voice"}:
            voice_source_type = "clean_voice"
        voice_profile_id = str(form.getfirst("voice_profile_id", "")).strip()
        return paths, voice_name, voice_source_type, voice_profile_id

    def send_html(self, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload: Dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_file(self, path: Path, head_only: bool = False, download_name: str | None = None) -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        file_size = path.stat().st_size
        range_header = self.headers.get("Range", "")
        start = 0
        end = file_size - 1
        status = HTTPStatus.OK

        if range_header.startswith("bytes="):
            range_value = range_header.removeprefix("bytes=").split(",", 1)[0]
            start_text, _, end_text = range_value.partition("-")
            try:
                if start_text:
                    start = int(start_text)
                if end_text:
                    end = int(end_text)
                end = min(end, file_size - 1)
                if start > end:
                    raise ValueError
                status = HTTPStatus.PARTIAL_CONTENT
            except ValueError:
                self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return

        content_length = end - start + 1
        filename = safe_download_filename(download_name, path.name)
        ascii_filename = safe_filename(filename)
        disposition = f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{quote(filename, safe='')}"
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Disposition", disposition)
        self.send_header("Content-Length", str(content_length))
        self.send_header("Accept-Ranges", "bytes")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.end_headers()
        if not head_only:
            with path.open("rb") as data:
                data.seek(start)
                self.wfile.write(data.read(content_length))

    def log_message(self, format: str, *args: object) -> None:
        print("%s - %s" % (self.address_string(), format % args))


def run_web_app(host: str, port: int, seed_vc_dir: Path) -> None:
    AppHandler.seed_vc_dir = seed_vc_dir
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Timbre Shift web app: http://{host}:{port}")
    server.serve_forever()


def write_error_metrics(path: Path, error: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "voice_profile_id": None,
                "voice_profile_name": None,
                "song_id": None,
                "song_title": None,
                "render_mode": None,
                "source_mode": None,
                "library_voice_hit": False,
                "library_song_stems_hit": False,
                "demucs_cache_hit": False,
                "seedvc_cache_hit": False,
                "song_duration_seconds": None,
                "active_vocal_seconds": None,
                "active_ratio": None,
                "prepare_voice_seconds": 0.0,
                "prepare_song_seconds": 0.0,
                "demucs_seconds": 0.0,
                "vocal_segment_detect_seconds": 0.0,
                "seedvc_seconds": 0.0,
                "restore_timeline_seconds": 0.0,
                "mix_seconds": 0.0,
                "mp3_export_seconds": 0.0,
                "total_seconds": 0.0,
                "seedvc_rtf": None,
                "mps_requested": False,
                "mps_used": False,
                "seedvc_device": None,
                "seedvc_cpu_fallback_used": False,
                "output_wav": None,
                "output_mp3": None,
                "error_message": error,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def create_test_result(path: Path) -> Path:
    """Create a short WAV so the upload/download flow is immediately testable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 44100
    duration_seconds = 3
    frequency = 440.0
    amplitude = 12000
    total_frames = sample_rate * duration_seconds

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for index in range(total_frames):
            sample = int(amplitude * math.sin(2 * math.pi * frequency * index / sample_rate))
            wav.writeframesraw(sample.to_bytes(2, byteorder="little", signed=True))
    return path
