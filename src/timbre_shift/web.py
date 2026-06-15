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
from typing import Dict, Tuple
from urllib.parse import parse_qs, quote, urlparse

from .demucs import separate_vocals
from .library import (
    DEFAULT_DB_PATH,
    DEFAULT_LIBRARY_DIR,
    add_voice_sample_to_profile,
    archive_voice_profile,
    init_library,
    list_voice_samples,
    list_voice_profiles,
    save_voice_to_library,
)
from .pipeline import PRESETS, PipelineOptions, check_environment, run_demo
from .vocal_segments import compact_for_conversion


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


def page_html() -> str:
    init_library(DEFAULT_DB_PATH)
    voice_options = "\n".join(
        f'<option value="{html.escape(profile.id)}">{html.escape(profile.name)}</option>'
        for profile in list_voice_profiles(only_allowed_targets=True, db_path=DEFAULT_DB_PATH)
    )
    body = """<!doctype html>
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
      width: min(640px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 36px 0;
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
      margin-top: 20px;
      display: grid;
      gap: 14px;
    }
    .section {
      display: grid;
      gap: 14px;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
    }
    .section-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .section-title h2 {
      margin: 0;
      font-size: 16px;
      line-height: 1.25;
      letter-spacing: 0;
    }
    .hint {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }
    .field {
      display: grid;
      gap: 8px;
      padding: 0;
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
    input[type="text"], select {
      width: 100%;
      min-height: 42px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      font-size: 14px;
    }
    details {
      border-top: 1px solid var(--line);
      padding-top: 12px;
    }
    summary {
      cursor: pointer;
      color: var(--accent);
      font-size: 14px;
      font-weight: 650;
      user-select: none;
    }
    .advanced-grid {
      display: grid;
      gap: 12px;
      margin-top: 12px;
    }
    .inline-fields {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      align-items: end;
    }
    .check {
      display: flex;
      align-items: flex-start;
      gap: 9px;
      color: var(--ink);
      font-size: 14px;
      font-weight: 500;
      line-height: 1.4;
    }
    .check input {
      margin-top: 2px;
      accent-color: var(--accent);
    }
    .radio-group {
      display: grid;
      gap: 8px;
    }
    .radio-group.two-column {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .option {
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 10px;
      min-height: 48px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      font-size: 14px;
      font-weight: 650;
      line-height: 1.35;
      cursor: pointer;
    }
    .option input {
      width: 18px;
      height: 18px;
      margin: 1px 0 0;
      accent-color: var(--accent);
    }
    .option span {
      display: block;
      margin-top: 3px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 500;
    }
    .native-select {
      display: none;
    }
    .voice-dropdown {
      position: relative;
    }
    .voice-trigger {
      width: 100%;
      min-height: 42px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      display: grid;
      grid-template-columns: 1fr auto;
      align-items: center;
      gap: 10px;
      font-size: 14px;
      font-weight: 650;
      text-align: left;
    }
    .voice-trigger:hover {
      border-color: var(--accent);
      background: #fff;
      color: var(--ink);
    }
    .voice-trigger::after {
      content: "⌄";
      color: var(--muted);
      font-size: 16px;
      line-height: 1;
    }
    .voice-menu {
      position: absolute;
      z-index: 20;
      top: calc(100% + 6px);
      left: 0;
      right: 0;
      display: none;
      max-height: 260px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      box-shadow: 0 12px 28px rgba(23, 32, 38, 0.14);
      padding: 6px;
    }
    .voice-dropdown.open .voice-menu {
      display: grid;
      gap: 6px;
    }
    .voice-row {
      display: grid;
      grid-template-columns: 1fr auto;
      align-items: center;
      gap: 8px;
      min-height: 38px;
      padding: 4px 4px 4px 8px;
      border-radius: 5px;
      background: #fff;
    }
    .voice-row.selected {
      background: #eef7f3;
    }
    .voice-empty {
      padding: 8px;
    }
    .voice-select {
      min-height: 30px;
      border: 0;
      background: transparent;
      color: var(--ink);
      font-size: 14px;
      font-weight: 650;
      text-align: left;
      justify-content: flex-start;
      padding: 0;
    }
    .voice-select:hover {
      background: transparent;
      color: var(--accent);
    }
    .voice-delete {
      min-height: 30px;
      padding: 0 10px;
      font-size: 13px;
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
    button.secondary {
      border-color: var(--line);
      background: #fff;
      color: var(--accent);
    }
    button.danger {
      border-color: #d33f49;
      background: #fff;
      color: #b4232c;
    }
    button:disabled {
      cursor: not-allowed;
      opacity: 0.55;
    }
    button.secondary:hover {
      border-color: var(--accent);
      background: #eef7f3;
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
      display: grid;
      gap: 14px;
    }
    .result-main {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    .metrics {
      width: 100%;
      display: none;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 10px;
      margin-top: 14px;
    }
    .metrics.visible { display: grid; }
    .metric {
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
    }
    .metric span {
      display: block;
      color: var(--muted);
      font-size: 12px;
    }
    .metric strong {
      display: block;
      margin-top: 3px;
      font-size: 15px;
      font-weight: 650;
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
      header, .actions, .result-main, .inline-fields {
        align-items: stretch;
        flex-direction: column;
        grid-template-columns: 1fr;
      }
      .radio-group.two-column { grid-template-columns: 1fr; }
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
      <section class="section">
        <div class="section-title">
          <h2>1. 音色</h2>
          <span class="hint" id="voiceHint">选一个音色</span>
        </div>
        <div class="field">
          <label for="voiceProfile">已保存音色</label>
          <select class="native-select" id="voiceProfile" name="voice_profile_id">
            <option value="">上传新声音</option>
            __VOICE_OPTIONS__
          </select>
          <div class="voice-dropdown" id="voiceDropdown">
            <button class="voice-trigger" id="voiceTrigger" type="button">上传新声音</button>
            <div class="voice-menu" id="voiceMenu"></div>
          </div>
        </div>
        <div class="field" id="voiceUploadField">
          <label for="voice">上传声音</label>
          <input id="voice" name="voice" type="file" accept="audio/*" multiple>
          <div class="hint" id="voiceFileSummary">可分多次选择，素材会累加</div>
        </div>
        <div class="field" id="voiceSourceField">
          <label>声音类型</label>
          <div class="radio-group two-column">
            <label class="option">
              <input type="radio" name="voice_source_type" value="clean_voice" checked>
              <span><strong>干净声音</strong><span>已经是单独人声，保存最快</span></span>
            </label>
            <label class="option">
              <input type="radio" name="voice_source_type" value="mixed_voice">
              <span><strong>歌曲/带伴奏声音</strong><span>高质量分离并筛选有效人声，较慢但更适合建音色</span></span>
            </label>
          </div>
        </div>
        <div class="inline-fields" id="voiceSaveActions">
          <div class="field" id="voiceNameField">
            <label for="voiceName">名称</label>
            <input id="voiceName" name="voice_name" type="text" placeholder="例如：我的声音">
          </div>
          <button class="secondary" id="saveVoiceButton" type="button">保存音色</button>
          <button class="secondary" id="addVoiceSampleButton" type="button">添加素材</button>
        </div>
        <div id="voiceSaveMessage" class="message"></div>
      </section>

      <section class="section">
        <div class="section-title">
          <h2>2. 歌曲</h2>
          <span class="hint" id="songHint">歌曲文件</span>
        </div>
        <div class="field" id="songUploadField">
          <label for="song">歌曲文件</label>
          <input id="song" name="song" type="file" accept="audio/*">
        </div>
      </section>

      <section class="section">
        <div class="section-title">
          <h2>3. 生成</h2>
          <span class="hint">默认整首模式</span>
        </div>
        <div class="field">
          <label>模式</label>
          <div class="radio-group two-column">
            <label class="option">
              <input type="radio" name="mode" value="m2max_hq_30" checked>
              <span><strong>默认整首</strong><span>速度和质量平衡</span></span>
            </label>
            <label class="option">
              <input type="radio" name="mode" value="preview_auto_15_m2max">
              <span><strong>15秒试听</strong><span>最快看效果</span></span>
            </label>
            <label class="option">
              <input type="radio" name="mode" value="m2max_hq_plus">
              <span><strong>高质量</strong><span>更细一点，会更慢</span></span>
            </label>
            <label class="option">
              <input type="radio" name="mode" value="m2max_offline_max">
              <span><strong>离线最高质量</strong><span>最慢，适合最终出片</span></span>
            </label>
          </div>
        </div>
      </section>
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
      <div class="result-main">
        <audio id="player" controls></audio>
        <a id="download" class="download" href="#" download>下载 MP3</a>
      </div>
      <details>
        <summary>结果详情</summary>
        <div class="advanced-grid">
          <a id="downloadWav" class="download" href="#" download>下载 WAV</a>
          <div id="metrics" class="metrics"></div>
        </div>
      </details>
    </section>
  </main>

  <script>
    const form = document.getElementById("form");
    const submit = document.getElementById("submit");
    const message = document.getElementById("message");
    const result = document.getElementById("result");
    const player = document.getElementById("player");
    const download = document.getElementById("download");
    const downloadWav = document.getElementById("downloadWav");
    const metrics = document.getElementById("metrics");
    const envStatus = document.getElementById("envStatus");
    const progress = document.getElementById("progress");
    const progressStep = document.getElementById("progressStep");
    const progressTime = document.getElementById("progressTime");
    const progressBar = document.getElementById("progressBar");
    const voiceProfile = document.getElementById("voiceProfile");
    const voiceDropdown = document.getElementById("voiceDropdown");
    const voiceTrigger = document.getElementById("voiceTrigger");
    const voiceMenu = document.getElementById("voiceMenu");
    const voiceInput = document.getElementById("voice");
    const voiceFileSummary = document.getElementById("voiceFileSummary");
    const voiceUploadField = document.getElementById("voiceUploadField");
    const voiceSourceField = document.getElementById("voiceSourceField");
    const voiceNameField = document.getElementById("voiceNameField");
    const voiceName = document.getElementById("voiceName");
    const saveVoiceButton = document.getElementById("saveVoiceButton");
    const addVoiceSampleButton = document.getElementById("addVoiceSampleButton");
    const voiceSaveActions = document.getElementById("voiceSaveActions");
    const voiceSaveMessage = document.getElementById("voiceSaveMessage");
    const voiceHint = document.getElementById("voiceHint");
    const songUploadField = document.getElementById("songUploadField");
    const songHint = document.getElementById("songHint");
    let progressPoller = null;
    let selectedVoiceFiles = [];

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

    function formatNumber(value, digits = 1) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
      return Number(value).toFixed(digits);
    }

    function renderMetrics(data) {
      const diagnostics = data.diagnostics || {};
      const suggestions = Array.isArray(diagnostics.suggestions) && diagnostics.suggestions.length
        ? diagnostics.suggestions.slice(0, 2).join("；")
        : "-";
      const items = [
        ["总用时", `${formatNumber(data.total_seconds)} 秒`],
        ["Demucs", `${formatNumber(data.demucs_seconds)} 秒`],
        ["Seed-VC", `${formatNumber(data.seedvc_seconds)} 秒`],
        ["有效人声", `${formatNumber(data.active_vocal_seconds)} 秒`],
        ["人声占比", data.active_ratio == null ? "-" : `${formatNumber(data.active_ratio * 100)}%`],
        ["Seed-VC RTF", formatNumber(data.seedvc_rtf, 2)],
        ["MPS", data.mps_used ? "是" : "否"],
        ["库分离命中", data.library_song_stems_hit ? "是" : "否"],
        ["Seed-VC缓存", data.seedvc_cache_hit ? "命中" : "未命中"],
        ["诊断", diagnostics.most_likely_issue || "未生成"],
        ["诊断置信度", diagnostics.confidence || "-"],
        ["建议", suggestions],
      ];
      metrics.innerHTML = items.map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`).join("");
      metrics.classList.add("visible");
    }

    function cleanDownloadName(value, fallback) {
      const cleaned = (value || "")
        .trim()
        .replace(/[\\/:*?"<>|]+/g, "-")
        .replace(/\s+/g, " ");
      if (!cleaned) return fallback;
      return cleaned.toLowerCase().endsWith(".mp3") ? cleaned : `${cleaned}.mp3`;
    }

    function voiceFileKey(file) {
      return `${file.name}:${file.size}:${file.lastModified}`;
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[char]));
    }

    function syncVoiceInputFiles() {
      if (typeof DataTransfer === "undefined") return;
      const transfer = new DataTransfer();
      selectedVoiceFiles.forEach((file) => transfer.items.add(file));
      voiceInput.files = transfer.files;
    }

    function renderVoiceFileSummary() {
      if (!selectedVoiceFiles.length) {
        voiceFileSummary.textContent = "可分多次选择，素材会累加";
        return;
      }
      const names = selectedVoiceFiles.slice(0, 3).map((file) => file.name).join("，");
      const suffix = selectedVoiceFiles.length > 3 ? ` 等 ${selectedVoiceFiles.length} 个` : ` 共 ${selectedVoiceFiles.length} 个`;
      voiceFileSummary.textContent = `已选：${names}${suffix}`;
    }

    function appendVoiceFiles(files) {
      const existing = new Set(selectedVoiceFiles.map(voiceFileKey));
      Array.from(files).forEach((file) => {
        const key = voiceFileKey(file);
        if (!existing.has(key)) {
          selectedVoiceFiles.push(file);
          existing.add(key);
        }
      });
      syncVoiceInputFiles();
      renderVoiceFileSummary();
    }

    function clearVoiceFiles() {
      selectedVoiceFiles = [];
      voiceInput.value = "";
      renderVoiceFileSummary();
    }

    function selectedVoiceLabel() {
      const selected = voiceProfile.options[voiceProfile.selectedIndex];
      return selected ? selected.textContent : "上传新声音";
    }

    function closeVoiceDropdown() {
      voiceDropdown.classList.remove("open");
    }

    function renderVoiceMenu() {
      voiceTrigger.textContent = selectedVoiceLabel();
      const options = Array.from(voiceProfile.options).filter((option) => option.value);
      const uploadRow = `
        <div class="voice-row ${voiceProfile.value ? "" : "selected"}" data-id="">
          <button class="voice-select" type="button" data-id="">上传新声音</button>
        </div>
      `;
      if (!options.length) {
        voiceMenu.innerHTML = `${uploadRow}<div class="hint voice-empty">还没有保存音色</div>`;
        return;
      }
      voiceMenu.innerHTML = uploadRow + options.map((option) => `
        <div class="voice-row ${option.selected ? "selected" : ""}" data-id="${escapeHtml(option.value)}">
          <button class="voice-select" type="button" data-id="${escapeHtml(option.value)}">${escapeHtml(option.textContent)}</button>
          <button class="danger voice-delete" type="button" data-id="${escapeHtml(option.value)}" data-name="${escapeHtml(option.textContent)}">删除</button>
        </div>
      `).join("");
    }

    function syncLibraryControls() {
      const usingSavedVoice = Boolean(voiceProfile.value);
      voiceUploadField.style.display = "grid";
      voiceSourceField.style.display = "grid";
      voiceNameField.style.display = "grid";
      voiceSaveActions.style.display = "grid";
      saveVoiceButton.style.display = usingSavedVoice ? "none" : "inline-flex";
      addVoiceSampleButton.style.display = usingSavedVoice ? "inline-flex" : "none";
      voiceHint.textContent = usingSavedVoice ? "可继续添加素材到当前音色" : "选择已有音色，或上传新声音";
      songUploadField.style.display = "grid";
      songHint.textContent = "上传要换声的音频";
      renderVoiceMenu();
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
      body.delete("voice");
      selectedVoiceFiles.forEach((file) => body.append("voice", file));
      if (!body.get("voice_profile_id") && !selectedVoiceFiles.length) {
        message.className = "message error";
        message.textContent = "请选择本地音色，或上传一个新声音样本";
        submit.disabled = false;
        stopProgressPolling();
        return;
      }
      if (!document.getElementById("song").files.length) {
        message.className = "message error";
        message.textContent = "请上传一个歌曲文件";
        submit.disabled = false;
        stopProgressPolling();
        return;
      }
      try {
        const response = await fetch("/api/generate", { method: "POST", body });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "生成失败");
        }
        const url = data.download_url + "?t=" + Date.now();
        const mp3Url = (data.download_mp3_url || data.download_url) + "?t=" + Date.now();
        const wavUrl = data.download_wav_url ? data.download_wav_url + "?t=" + Date.now() : url;
        player.src = mp3Url;
        player.load();
        download.href = mp3Url;
        download.download = data.mp3_filename || "final.mp3";
        downloadWav.href = wavUrl;
        downloadWav.download = data.wav_filename || "final.wav";
        if (data.metrics) renderMetrics(data.metrics);
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

    download.addEventListener("click", (event) => {
      if (!download.href || download.href.endsWith("#")) {
        event.preventDefault();
        return;
      }
      const currentName = download.download || "final.mp3";
      const name = window.prompt("输出 MP3 文件名", currentName);
      if (name === null) {
        event.preventDefault();
        return;
      }
      const cleanedName = cleanDownloadName(name, currentName);
      const url = new URL(download.href);
      url.searchParams.set("name", cleanedName);
      download.href = url.toString();
      download.download = cleanedName;
    });

    saveVoiceButton.addEventListener("click", async () => {
      voiceSaveMessage.className = "message";
      voiceSaveMessage.textContent = "保存中...";
      saveVoiceButton.disabled = true;
      try {
        const voiceFiles = selectedVoiceFiles;
        if (!voiceFiles.length) {
          throw new Error("先选择一个或多个声音样本");
        }
        const body = new FormData();
        voiceFiles.forEach((file) => body.append("voice", file));
        body.append("voice_name", voiceName.value || voiceFiles[0].name);
        body.append("voice_source_type", form.elements["voice_source_type"].value);
        const response = await fetch("/api/save-voice", { method: "POST", body });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "保存失败");
        }
        const option = document.createElement("option");
        option.value = data.id;
        option.textContent = data.name;
        option.selected = true;
        voiceProfile.appendChild(option);
        voiceSaveMessage.textContent = data.added_count > 1 ? `已保存，素材数 ${data.sample_count}` : "已保存";
        clearVoiceFiles();
        syncLibraryControls();
      } catch (error) {
        voiceSaveMessage.className = "message error";
        voiceSaveMessage.textContent = error.message;
      } finally {
        saveVoiceButton.disabled = false;
      }
    });

    addVoiceSampleButton.addEventListener("click", async () => {
      const id = voiceProfile.value;
      voiceSaveMessage.className = "message";
      voiceSaveMessage.textContent = "添加中...";
      addVoiceSampleButton.disabled = true;
      try {
        if (!id) {
          throw new Error("先选择一个已保存音色");
        }
        const voiceFiles = selectedVoiceFiles;
        if (!voiceFiles.length) {
          throw new Error("先选择一个或多个声音素材");
        }
        const body = new FormData();
        body.append("voice_profile_id", id);
        voiceFiles.forEach((file) => body.append("voice", file));
        body.append("voice_name", voiceName.value || voiceFiles[0].name);
        body.append("voice_source_type", form.elements["voice_source_type"].value);
        const response = await fetch("/api/add-voice-sample", { method: "POST", body });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "添加失败");
        }
        voiceSaveMessage.textContent = `已添加素材，总数 ${data.sample_count}`;
        voiceName.value = "";
        clearVoiceFiles();
      } catch (error) {
        voiceSaveMessage.className = "message error";
        voiceSaveMessage.textContent = error.message;
      } finally {
        addVoiceSampleButton.disabled = false;
        syncLibraryControls();
      }
    });

    voiceTrigger.addEventListener("click", () => {
      voiceDropdown.classList.toggle("open");
    });

    document.addEventListener("click", (event) => {
      if (!voiceDropdown.contains(event.target)) {
        closeVoiceDropdown();
      }
    });

    voiceMenu.addEventListener("click", async (event) => {
      const selectButton = event.target.closest(".voice-select");
      const deleteButton = event.target.closest(".voice-delete");
      if (selectButton) {
        voiceProfile.value = selectButton.dataset.id;
        closeVoiceDropdown();
        syncLibraryControls();
        return;
      }
      if (!deleteButton) return;
      const id = deleteButton.dataset.id;
      const name = deleteButton.dataset.name || "这个音色";
      if (!window.confirm(`删除已保存音色「${name}」？`)) return;
      deleteButton.disabled = true;
      voiceSaveMessage.className = "message";
      voiceSaveMessage.textContent = "删除中...";
      try {
        const body = new FormData();
        body.append("voice_profile_id", id);
        const response = await fetch("/api/delete-voice", { method: "POST", body });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "删除失败");
        }
        const selectedOption = Array.from(voiceProfile.options).find((option) => option.value === id);
        if (selectedOption) selectedOption.remove();
        if (voiceProfile.value === id) {
          voiceProfile.value = "";
        }
        voiceSaveMessage.textContent = "已删除";
        closeVoiceDropdown();
        syncLibraryControls();
      } catch (error) {
        voiceSaveMessage.className = "message error";
        voiceSaveMessage.textContent = error.message;
      } finally {
        syncLibraryControls();
      }
    });

    refreshEnv().catch(() => {
      envStatus.textContent = "环境检查失败";
    });
    voiceInput.addEventListener("change", () => appendVoiceFiles(voiceInput.files));
    voiceProfile.addEventListener("change", syncLibraryControls);
    renderVoiceFileSummary();
    syncLibraryControls();
  </script>
</body>
</html>"""
    return body.replace("__VOICE_OPTIONS__", voice_options)


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
