"""Tiny local web UI for the first Timbre Shift demo."""

from __future__ import annotations

import json
import mimetypes
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict
from urllib.parse import parse_qs, quote, urlparse

from .generation_history import list_generation_history
from .history_actions import delete_history_job, restore_history_job
from .library import (
    DEFAULT_DB_PATH,
    DEFAULT_LIBRARY_DIR,
    archive_song,
    archive_voice_sample,
    archive_voice_model,
    archive_voice_profile,
    create_empty_voice_profile,
    list_voice_samples,
    list_voice_models,
    refresh_voice_profile_references,
)
from .pipeline import check_environment
from .variant_actions import record_variant_feedback, select_variant
from .voice_preferences import save_voice_preference
from .web_generation import generate_song_payload
from .web_queries import voice_models_payload, voice_preference_payload, voice_samples_payload
from .web_results import build_latest_result_response, create_test_result, write_error_metrics
from .web_serializers import serialize_voice_sample
from .web_state import PROGRESS
from .web_template import page_html
from .web_training import prepare_applio_payload, train_applio_payload
from .web_uploads import (
    read_form_fields as parse_form_fields,
    read_uploads as parse_uploads,
    read_voice_library_upload as parse_voice_library_upload,
    read_voice_sample_upload as parse_voice_sample_upload,
)
from .web_utils import safe_download_filename, safe_filename
from .web_voice_tasks import add_voice_samples_from_uploads, save_voice_profile_from_uploads


ROOT = Path.cwd()
UPLOAD_ROOT = ROOT / "data" / "raw" / "web_uploads"
OUTPUT_DIR = ROOT / "outputs" / "web"
HISTORY_ROOT = ROOT / "outputs" / "history"
STATIC_ROOT = Path(__file__).with_name("web_static")


def safe_history_job_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "", value)


class AppHandler(BaseHTTPRequestHandler):
    seed_vc_dir: Path = Path("vendor/seed-vc")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        request_path = parsed.path
        if request_path == "/":
            self.send_html(page_html())
            return
        if request_path.startswith("/static/"):
            self.send_static_file(request_path.removeprefix("/static/"))
            return
        if request_path == "/api/check":
            report = check_environment(self.seed_vc_dir)
            self.send_json({"ready": report.ready, "missing": report.missing, "text": report.to_text()})
            return
        if request_path == "/api/progress":
            self.send_json(PROGRESS.snapshot())
            return
        if request_path == "/api/history":
            self.send_json({"jobs": list_generation_history(HISTORY_ROOT)})
            return
        if request_path == "/api/latest-result":
            try:
                self.send_json(build_latest_result_response(OUTPUT_DIR))
            except FileNotFoundError as exc:
                self.send_json({"error": str(exc)}, status=HTTPStatus.NOT_FOUND)
            return
        if request_path == "/api/voice-preference":
            query = parse_qs(parsed.query)
            voice_id = (query.get("voice_id") or [""])[0]
            self.send_json(voice_preference_payload(voice_id))
            return
        if request_path == "/api/voice-samples":
            query = parse_qs(parsed.query)
            voice_id = (query.get("voice_id") or [""])[0]
            self.send_json(voice_samples_payload(voice_id))
            return
        if request_path == "/api/voice-models":
            query = parse_qs(parsed.query)
            voice_id = (query.get("voice_id") or [""])[0]
            engine_id = (query.get("engine_id") or ["rvc_applio"])[0]
            self.send_json(voice_models_payload(voice_id, engine_id))
            return
        if request_path.startswith("/download/history/"):
            raw_parts = [part for part in request_path.removeprefix("/download/history/").split("/") if part]
            if len(raw_parts) != 2:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            parts = [safe_history_job_id(raw_parts[0]), safe_filename(raw_parts[1])]
            download_name = parse_qs(parsed.query).get("name", [None])[0]
            self.send_file(HISTORY_ROOT / parts[0] / parts[1], download_name=download_name)
            return
        if request_path.startswith("/download/variants/"):
            download_name = parse_qs(parsed.query).get("name", [None])[0]
            self.send_file(
                OUTPUT_DIR / "variants" / safe_filename(request_path.removeprefix("/download/variants/")),
                download_name=download_name,
            )
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
        if request_path.startswith("/static/"):
            self.send_static_file(request_path.removeprefix("/static/"), head_only=True)
            return
        if request_path.startswith("/download/history/"):
            raw_parts = [part for part in request_path.removeprefix("/download/history/").split("/") if part]
            if len(raw_parts) != 2:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            parts = [safe_history_job_id(raw_parts[0]), safe_filename(raw_parts[1])]
            download_name = parse_qs(parsed.query).get("name", [None])[0]
            self.send_file(HISTORY_ROOT / parts[0] / parts[1], head_only=True, download_name=download_name)
            return
        if request_path.startswith("/download/variants/"):
            download_name = parse_qs(parsed.query).get("name", [None])[0]
            self.send_file(
                OUTPUT_DIR / "variants" / safe_filename(request_path.removeprefix("/download/variants/")),
                head_only=True,
                download_name=download_name,
            )
            return
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
        if self.path == "/api/cancel-task":
            PROGRESS.cancel()
            self.send_json({"message": "已请求停止当前任务", "progress": PROGRESS.snapshot()})
            return
        if self.path == "/api/voice-preference":
            try:
                fields = self.read_form_fields()
                voice_profile_id = str(fields.get("voice_profile_id", "")).strip()
                preference = save_voice_preference(
                    voice_profile_id,
                    {
                        "voice_profile_id": voice_profile_id,
                        "engine_id": fields.get("engine_id"),
                        "rvc_goal": fields.get("rvc_goal") or fields.get("rvc_preset"),
                        "diction_mode": fields.get("diction_mode"),
                        "vocal_style": fields.get("vocal_style"),
                        "rvc_index_enabled": fields.get("rvc_index_enabled") in {"1", "true", "on"},
                        "rvc_index_rate": fields.get("rvc_index_rate"),
                        "mix_style": fields.get("mix_style"),
                        "pre_rvc_cleanup_mode": fields.get("pre_rvc_cleanup_mode"),
                        "selected_variant": fields.get("selected_variant"),
                    },
                )
                self.send_json({"message": "已保存为该音色默认参数", "preference": preference})
            except Exception as exc:
                self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        if self.path == "/api/history-restore":
            try:
                fields = self.read_form_fields()
                job_id = safe_filename(str(fields.get("job_id", "")))
                self.send_json(restore_history_job(HISTORY_ROOT, OUTPUT_DIR, job_id))
            except Exception as exc:
                self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        if self.path == "/api/history-delete":
            try:
                fields = self.read_form_fields()
                job_id = safe_filename(str(fields.get("job_id", "")))
                self.send_json(delete_history_job(HISTORY_ROOT, job_id))
            except Exception as exc:
                self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        if self.path == "/api/select-variant":
            try:
                fields = self.read_form_fields()
                variant_id = safe_filename(str(fields.get("variant_id", "")))
                self.send_json(select_variant(OUTPUT_DIR, variant_id))
            except Exception as exc:
                self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        if self.path == "/api/variant-feedback":
            try:
                fields = self.read_form_fields()
                variant_id = safe_filename(str(fields.get("variant_id", "")))
                self.send_json(record_variant_feedback(OUTPUT_DIR, variant_id))
            except Exception as exc:
                self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        if self.path == "/api/add-voice-sample":
            try:
                voice_uploads, voice_name, voice_source_type, voice_profile_id = self.read_voice_sample_upload()
                self.send_json(
                    add_voice_samples_from_uploads(
                        voice_uploads,
                        voice_name,
                        voice_source_type,
                        voice_profile_id,
                        ROOT,
                    )
                )
            except Exception as exc:
                if PROGRESS.is_cancelled():
                    PROGRESS.cancel()
                else:
                    PROGRESS.fail(str(exc))
                self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        if self.path == "/api/delete-voice-sample":
            try:
                fields = self.read_form_fields()
                voice_id = str(fields.get("voice_profile_id", "")).strip()
                sample_id = str(fields.get("sample_id", "")).strip()
                if not voice_id or not sample_id:
                    raise ValueError("请选择要删除的素材")
                archive_voice_sample(sample_id, db_path=DEFAULT_DB_PATH)
                refresh_voice_profile_references(voice_id, library_dir=DEFAULT_LIBRARY_DIR, db_path=DEFAULT_DB_PATH)
                samples = list_voice_samples(voice_id, db_path=DEFAULT_DB_PATH)
                self.send_json(
                    {
                        "message": "素材已删除",
                        "sample_count": len(samples),
                        "samples": [serialize_voice_sample(sample) for sample in samples],
                    }
                )
            except Exception as exc:
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
                if PROGRESS.is_cancelled():
                    PROGRESS.cancel()
                else:
                    PROGRESS.fail(str(exc))
                self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        if self.path == "/api/delete-song":
            try:
                fields = self.read_form_fields()
                song_id = str(fields.get("song_id", "")).strip()
                if not song_id:
                    raise ValueError("请选择要删除的歌曲")
                archive_song(song_id, db_path=DEFAULT_DB_PATH)
                self.send_json({"id": song_id, "message": "歌曲已删除"})
            except Exception as exc:
                self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        if self.path == "/api/delete-voice-model":
            try:
                fields = self.read_form_fields()
                model_id = str(fields.get("voice_model_id", "")).strip()
                if not model_id:
                    raise ValueError("请选择要删除的模型")
                archive_voice_model(model_id, db_path=DEFAULT_DB_PATH)
                self.send_json({"id": model_id, "message": "模型已删除"})
            except Exception as exc:
                if PROGRESS.is_cancelled():
                    PROGRESS.cancel()
                else:
                    PROGRESS.fail(str(exc))
                self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        if self.path == "/api/create-voice-profile":
            try:
                fields = self.read_form_fields()
                voice_name = str(fields.get("voice_name", "")).strip() or "未命名音色库"
                profile = create_empty_voice_profile(
                    name=voice_name,
                    description="RVC training library",
                    library_dir=DEFAULT_LIBRARY_DIR,
                    db_path=DEFAULT_DB_PATH,
                )
                self.send_json(
                    {
                        "id": profile.id,
                        "name": profile.name,
                        "source_type": profile.source_type,
                        "sample_count": 0,
                        "added_count": 0,
                        "message": "音色库已创建，请添加训练素材",
                    }
                )
            except Exception as exc:
                if PROGRESS.is_cancelled():
                    PROGRESS.cancel()
                else:
                    PROGRESS.fail(str(exc))
                self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        if self.path == "/api/applio-prepare":
            try:
                fields = self.read_form_fields()
                self.send_json(prepare_applio_payload(fields))
            except Exception as exc:
                if PROGRESS.is_cancelled():
                    PROGRESS.cancel()
                else:
                    PROGRESS.fail(str(exc))
                self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        if self.path == "/api/applio-train":
            try:
                fields = self.read_form_fields()
                self.send_json(train_applio_payload(fields))
            except Exception as exc:
                if PROGRESS.is_cancelled():
                    PROGRESS.cancel()
                else:
                    PROGRESS.fail(str(exc))
                self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        if self.path == "/api/save-voice":
            try:
                voice_uploads, voice_name, voice_source_type = self.read_voice_library_upload()
                self.send_json(save_voice_profile_from_uploads(voice_uploads, voice_name, voice_source_type, ROOT))
            except Exception as exc:
                if PROGRESS.is_cancelled():
                    PROGRESS.cancel()
                else:
                    PROGRESS.fail(str(exc))
                self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        if self.path != "/api/generate":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            PROGRESS.reset("接收上传文件", 1, "running")
            files, fields = self.read_uploads()
            payload = generate_song_payload(
                seed_vc_dir=self.seed_vc_dir,
                files=files,
                fields=fields,
                root=ROOT,
                output_dir=OUTPUT_DIR,
            )
            if payload.get("mode") == "real":
                message = "歌曲生成完成"
                payload["message"] = message
            self.send_json(payload)
        except BrokenPipeError as exc:
            if PROGRESS.snapshot().get("status") == "completed":
                return
            PROGRESS.fail(str(exc))
            write_error_metrics(OUTPUT_DIR / "metrics.json", str(exc))
        except Exception as exc:
            if PROGRESS.is_cancelled():
                PROGRESS.cancel()
            else:
                PROGRESS.fail(str(exc))
            write_error_metrics(OUTPUT_DIR / "metrics.json", str(exc))
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def read_uploads(self) -> tuple[dict[str, Path], dict[str, object]]:
        return parse_uploads(self.rfile, self.headers, UPLOAD_ROOT)

    def read_form_fields(self) -> Dict[str, object]:
        return parse_form_fields(self.rfile, self.headers)

    def read_voice_library_upload(self) -> tuple[list[Path], str, str]:
        return parse_voice_library_upload(self.rfile, self.headers, UPLOAD_ROOT)

    def read_voice_sample_upload(self) -> tuple[list[Path], str, str, str]:
        return parse_voice_sample_upload(self.rfile, self.headers, UPLOAD_ROOT)

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

    def send_static_file(self, relative_path: str, head_only: bool = False) -> None:
        if not relative_path or "\x00" in relative_path:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        static_root = STATIC_ROOT.resolve()
        path = (static_root / relative_path).resolve()
        try:
            path.relative_to(static_root)
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if not head_only:
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
