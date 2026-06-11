"""Tiny local web UI for the first Timbre Shift demo."""

from __future__ import annotations

import cgi
import html
import json
import math
import mimetypes
import re
import threading
import time
import wave
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Optional, Tuple

from .pipeline import PipelineOptions, check_environment, run_demo


ROOT = Path.cwd()
UPLOAD_ROOT = ROOT / "data" / "raw" / "web_uploads"
OUTPUT_DIR = ROOT / "outputs" / "web"


class ProgressState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset("待命", 0, "idle")

    def reset(self, step: str, percent: int, status: str) -> None:
        with self._lock:
            now = time.time()
            self.started_at = now
            self.updated_at = now
            self.step = step
            self.percent = percent
            self.status = status
            self.error = ""

    def update(self, step: str, percent: int, status: str = "running") -> None:
        with self._lock:
            self.step = step
            self.percent = percent
            self.status = status
            self.updated_at = time.time()

    def fail(self, error: str) -> None:
        with self._lock:
            self.step = "生成失败"
            self.percent = max(self.percent, 1)
            self.status = "failed"
            self.error = error
            self.updated_at = time.time()

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            now = time.time()
            return {
                "step": self.step,
                "percent": self.percent,
                "status": self.status,
                "error": self.error,
                "elapsed_seconds": int(now - self.started_at) if self.status != "idle" else 0,
                "updated_seconds_ago": int(now - self.updated_at),
            }


PROGRESS = ProgressState()


def safe_filename(name: str) -> str:
    path_name = Path(name).name
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", Path(path_name).stem).strip("-")
    suffix = re.sub(r"[^A-Za-z0-9.]+", "", Path(path_name).suffix)
    return f"{stem or 'upload'}{suffix or '.wav'}"


def page_html() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Timbre Shift</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #172026;
      --muted: #596670;
      --line: #d8dee4;
      --paper: #f7f8f5;
      --panel: #ffffff;
      --accent: #13795b;
      --accent-strong: #0d5f48;
      --warn: #8a4b00;
      --error: #9f1d1d;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--paper);
    }
    main {
      width: min(760px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 48px 0;
    }
    header {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 16px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--line);
    }
    h1 {
      margin: 0;
      min-width: 180px;
      font-size: 28px;
      line-height: 1.15;
      letter-spacing: 0;
    }
    .status {
      flex: 1;
      color: var(--muted);
      font-size: 14px;
      text-align: right;
    }
    form {
      margin-top: 28px;
      display: grid;
      gap: 18px;
    }
    .field {
      display: grid;
      gap: 8px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
    }
    label {
      font-size: 15px;
      font-weight: 650;
    }
    input[type="file"] {
      width: 100%;
      min-height: 42px;
      padding: 8px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      font-size: 14px;
    }
    .option {
      display: flex;
      align-items: center;
      gap: 10px;
      min-height: 44px;
      padding: 0 2px;
      color: var(--ink);
      font-size: 15px;
      font-weight: 650;
    }
    .option input {
      width: 18px;
      height: 18px;
      accent-color: var(--accent);
    }
    .actions {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 2px;
    }
    button, .download {
      min-height: 42px;
      padding: 0 18px;
      border: 1px solid var(--accent);
      border-radius: 6px;
      background: var(--accent);
      color: #fff;
      font-size: 15px;
      font-weight: 650;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
    button:hover, .download:hover { background: var(--accent-strong); }
    button:disabled {
      opacity: 0.65;
      cursor: wait;
    }
    .message {
      min-height: 22px;
      color: var(--muted);
      font-size: 14px;
    }
    .message.error { color: var(--error); }
    .message.warn { color: var(--warn); }
    .result {
      margin-top: 22px;
      padding-top: 18px;
      border-top: 1px solid var(--line);
      display: none;
    }
    .result.visible {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 14px;
    }
    audio {
      width: min(420px, 100%);
      height: 40px;
    }
    .progress {
      display: none;
      margin-top: 4px;
      padding: 14px 0 2px;
      gap: 8px;
    }
    .progress.visible {
      display: grid;
    }
    .progress-meta {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      color: var(--muted);
      font-size: 14px;
    }
    .progress-track {
      width: 100%;
      height: 10px;
      overflow: hidden;
      border-radius: 999px;
      background: #e7ebe7;
      border: 1px solid var(--line);
    }
    .progress-bar {
      width: 0%;
      height: 100%;
      background: var(--accent);
      transition: width 180ms ease;
    }
    @media (max-width: 640px) {
      main { padding: 28px 0; }
      header, .actions, .result.visible {
        align-items: stretch;
        flex-direction: column;
      }
      .status { white-space: normal; }
      button, .download { width: 100%; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Timbre Shift</h1>
      <div class="status" id="envStatus">检查环境中...</div>
    </header>

    <form id="form">
      <div class="field">
        <label for="voice">你的声音样本</label>
        <input id="voice" name="voice" type="file" accept="audio/*" required>
      </div>
      <div class="field">
        <label for="song">歌曲文件</label>
        <input id="song" name="song" type="file" accept="audio/*" required>
      </div>
      <label class="option" for="preview">
        <input id="preview" name="preview" type="checkbox" checked>
        <span>30秒试听</span>
      </label>
      <div class="actions">
        <button id="submit" type="submit">生成</button>
        <div id="message" class="message"></div>
      </div>
      <div id="progress" class="progress">
        <div class="progress-meta">
          <span id="progressStep">待命</span>
          <span id="progressTime">00:00</span>
        </div>
        <div class="progress-track">
          <div id="progressBar" class="progress-bar"></div>
        </div>
      </div>
    </form>

    <section id="result" class="result">
      <audio id="player" controls></audio>
      <a id="download" class="download" href="#" download>下载</a>
    </section>
  </main>

  <script>
    const form = document.getElementById("form");
    const submit = document.getElementById("submit");
    const message = document.getElementById("message");
    const result = document.getElementById("result");
    const player = document.getElementById("player");
    const download = document.getElementById("download");
    const envStatus = document.getElementById("envStatus");
    const progress = document.getElementById("progress");
    const progressStep = document.getElementById("progressStep");
    const progressTime = document.getElementById("progressTime");
    const progressBar = document.getElementById("progressBar");
    let progressPoller = null;

    function formatDuration(seconds) {
      const mins = Math.floor(seconds / 60).toString().padStart(2, "0");
      const secs = Math.floor(seconds % 60).toString().padStart(2, "0");
      return `${mins}:${secs}`;
    }

    function friendlyMissing(item) {
      if (item.includes("seed-vc") || item.includes("inference.py")) {
        return "Seed-VC";
      }
      return item;
    }

    async function refreshEnv() {
      const response = await fetch("/api/check");
      const data = await response.json();
      if (data.ready) {
        envStatus.textContent = "环境就绪";
      } else {
        envStatus.textContent = "缺少：" + data.missing.map(friendlyMissing).join("，");
      }
    }

    async function refreshProgress() {
      const response = await fetch("/api/progress");
      const data = await response.json();
      progress.classList.add("visible");
      progressStep.textContent = `${data.step} · ${data.percent}%`;
      progressTime.textContent = `用时 ${formatDuration(data.elapsed_seconds || 0)}`;
      progressBar.style.width = `${Math.max(0, Math.min(100, data.percent || 0))}%`;
      return data;
    }

    function startProgressPolling() {
      progress.classList.add("visible");
      progressStep.textContent = "准备开始 · 0%";
      progressTime.textContent = "用时 00:00";
      progressBar.style.width = "0%";
      if (progressPoller) {
        clearInterval(progressPoller);
      }
      progressPoller = setInterval(() => {
        refreshProgress().catch(() => {});
      }, 1000);
    }

    function stopProgressPolling() {
      if (progressPoller) {
        clearInterval(progressPoller);
        progressPoller = null;
      }
      refreshProgress().catch(() => {});
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      result.classList.remove("visible");
      message.className = "message";
      message.textContent = "生成中...";
      startProgressPolling();
      submit.disabled = true;
      const body = new FormData(form);
      try {
        const response = await fetch("/api/generate", { method: "POST", body });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "生成失败");
        }
        const url = data.download_url + "?t=" + Date.now();
        player.src = url;
        download.href = url;
        download.download = data.filename || "final.wav";
        result.classList.add("visible");
        message.className = data.mode === "test" ? "message warn" : "message";
        message.textContent = data.message || "生成完成";
        progressStep.textContent = `生成完成 · 100%`;
        progressBar.style.width = "100%";
      } catch (error) {
        message.className = "message error";
        message.textContent = error.message;
      } finally {
        submit.disabled = false;
        stopProgressPolling();
      }
    });

    refreshEnv().catch(() => {
      envStatus.textContent = "环境检查失败";
    });
  </script>
</body>
</html>"""


class AppHandler(BaseHTTPRequestHandler):
    seed_vc_dir: Path = Path("vendor/seed-vc")

    def do_GET(self) -> None:
        if self.path == "/" or self.path.startswith("/?"):
            self.send_html(page_html())
            return
        if self.path == "/api/check":
            report = check_environment(self.seed_vc_dir)
            self.send_json({"ready": report.ready, "missing": report.missing, "text": report.to_text()})
            return
        if self.path == "/api/progress":
            self.send_json(PROGRESS.snapshot())
            return
        if self.path.startswith("/download/"):
            self.send_file(OUTPUT_DIR / safe_filename(self.path.removeprefix("/download/")))
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/api/generate":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            PROGRESS.reset("接收上传文件", 1, "running")
            files, clip_seconds = self.read_uploads()
            PROGRESS.update("检查运行环境", 3)
            report = check_environment(self.seed_vc_dir)
            if report.ready:
                final_mix = run_demo(
                    PipelineOptions(
                        voice=files["voice"],
                        song=files["song"],
                        seed_vc_dir=self.seed_vc_dir,
                        work_dir=ROOT / "data" / "processed" / "web",
                        output_dir=OUTPUT_DIR,
                        clip_seconds=clip_seconds,
                    ),
                    progress=lambda step, percent: PROGRESS.update(step, percent),
                )
                PROGRESS.update("生成完成", 100, "completed")
                message = "30秒试听生成完成" if clip_seconds else "生成完成"
                self.send_json(
                    {
                        "download_url": f"/download/{final_mix.name}",
                        "filename": final_mix.name,
                        "mode": "real",
                        "message": message,
                        "clip_seconds": clip_seconds,
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
        except Exception as exc:
            PROGRESS.fail(str(exc))
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def read_uploads(self) -> Tuple[Dict[str, Path], Optional[int]]:
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
            item = form[field] if field in form else None
            if item is None or not getattr(item, "filename", ""):
                raise ValueError(f"缺少文件：{field}")
            filename = safe_filename(item.filename)
            path = target_dir / f"{field}-{filename}"
            with path.open("wb") as output:
                while True:
                    chunk = item.file.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
            saved[field] = path
        preview_value = form.getfirst("preview", "")
        clip_seconds = 30 if preview_value else None
        return saved, clip_seconds

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

    def send_file(self, path: Path) -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Disposition", f'attachment; filename="{html.escape(path.name)}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        print("%s - %s" % (self.address_string(), format % args))


def run_web_app(host: str, port: int, seed_vc_dir: Path) -> None:
    AppHandler.seed_vc_dir = seed_vc_dir
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Timbre Shift web app: http://{host}:{port}")
    server.serve_forever()


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
