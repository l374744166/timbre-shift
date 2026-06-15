"""HTML shell for the local Timbre Shift web UI."""

from __future__ import annotations

import html

from .library import DEFAULT_DB_PATH, init_library, list_voice_profiles


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
    .train-panel {
      display: none;
      gap: 8px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fbfcfb;
    }
    .train-panel.visible {
      display: grid;
    }
    .train-actions {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
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
    .selected-file-list {
      display: grid;
      gap: 6px;
    }
    .selected-file-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: center;
      gap: 8px;
      min-height: 34px;
      padding: 5px 5px 5px 9px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      font-size: 13px;
      line-height: 1.3;
    }
    .selected-file-name {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .file-remove {
      min-height: 26px;
      padding: 0 9px;
      font-size: 12px;
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
      .train-actions { grid-template-columns: 1fr; }
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
          <div class="selected-file-list" id="voiceFileList"></div>
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
          <div class="selected-file-list" id="songFileSummary"></div>
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
        <div class="field">
          <label>转换引擎</label>
          <div class="radio-group two-column">
            <label class="option">
              <input type="radio" name="engine_id" value="seedvc" checked>
              <span><strong>Seed-VC</strong><span>零样本，不需要训练，适合试听和当前主流程</span></span>
            </label>
            <label class="option">
              <input type="radio" name="engine_id" value="rvc_applio">
              <span><strong>Applio RVC</strong><span>需要训练模型，适合多素材高要求音色</span></span>
            </label>
          </div>
        </div>
        <div class="field" id="voiceModelField">
          <label for="voiceModel">模型</label>
          <select id="voiceModel" name="voice_model_id">
            <option value="">Seed-VC 默认参考音色</option>
          </select>
          <div class="hint" id="voiceModelHint">Seed-VC 会直接使用当前音色参考音频</div>
          <div class="train-panel" id="applioTrainPanel">
            <div class="train-actions">
              <button class="secondary" id="prepareApplioButton" type="button">准备数据集</button>
              <button class="secondary" id="trainApplioButton" type="button">训练模型</button>
            </div>
            <div class="hint">默认 120 epoch / batch 4，训练完成后模型会自动出现在下拉框</div>
            <div id="applioTrainMessage" class="message"></div>
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
    const voiceFileList = document.getElementById("voiceFileList");
    const voiceUploadField = document.getElementById("voiceUploadField");
    const voiceSourceField = document.getElementById("voiceSourceField");
    const voiceNameField = document.getElementById("voiceNameField");
    const voiceName = document.getElementById("voiceName");
    const saveVoiceButton = document.getElementById("saveVoiceButton");
    const addVoiceSampleButton = document.getElementById("addVoiceSampleButton");
    const voiceSaveActions = document.getElementById("voiceSaveActions");
    const voiceSaveMessage = document.getElementById("voiceSaveMessage");
    const voiceHint = document.getElementById("voiceHint");
    const voiceModelField = document.getElementById("voiceModelField");
    const voiceModel = document.getElementById("voiceModel");
    const voiceModelHint = document.getElementById("voiceModelHint");
    const applioTrainPanel = document.getElementById("applioTrainPanel");
    const prepareApplioButton = document.getElementById("prepareApplioButton");
    const trainApplioButton = document.getElementById("trainApplioButton");
    const applioTrainMessage = document.getElementById("applioTrainMessage");
    const songInput = document.getElementById("song");
    const songUploadField = document.getElementById("songUploadField");
    const songFileSummary = document.getElementById("songFileSummary");
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
        ["转换引擎", data.engine_name || data.engine_id || "Seed-VC"],
        ["总用时", `${formatNumber(data.total_seconds)} 秒`],
        ["Demucs", `${formatNumber(data.demucs_seconds)} 秒`],
        ["转换", `${formatNumber(data.convert_seconds || data.seedvc_seconds)} 秒`],
        ["分段换声", data.seedvc_chunked_used ? `${data.seedvc_chunk_seconds || "-"}秒 / ${data.seedvc_chunk_workers || 1}路` : (data.seedvc_chunked_attempted ? "已回退整段" : "未启用")],
        ["有效人声", `${formatNumber(data.active_vocal_seconds)} 秒`],
        ["人声占比", data.active_ratio == null ? "-" : `${formatNumber(data.active_ratio * 100)}%`],
        ["转换 RTF", formatNumber(data.seedvc_rtf, 2)],
        ["MPS", data.mps_used ? "是" : "否"],
        ["库分离命中", data.library_song_stems_hit ? "是" : "否"],
        ["Seed-VC缓存", data.seedvc_cache_hit ? "命中" : "未命中"],
        ["训练模型", data.trained_model_status || data.rvc_mlx_status || "未使用"],
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
        voiceFileList.innerHTML = "";
        return;
      }
      const names = selectedVoiceFiles.slice(0, 3).map((file) => file.name).join("，");
      const suffix = selectedVoiceFiles.length > 3 ? ` 等 ${selectedVoiceFiles.length} 个` : ` 共 ${selectedVoiceFiles.length} 个`;
      voiceFileSummary.textContent = `已选：${names}${suffix}`;
      voiceFileList.innerHTML = selectedVoiceFiles.map((file, index) => `
        <div class="selected-file-row">
          <span class="selected-file-name">${escapeHtml(file.name)}</span>
          <button class="danger file-remove" type="button" data-index="${index}">移除</button>
        </div>
      `).join("");
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
      syncVoiceInputFiles();
      renderVoiceFileSummary();
    }

    function removeVoiceFile(index) {
      selectedVoiceFiles.splice(index, 1);
      syncVoiceInputFiles();
      renderVoiceFileSummary();
    }

    function renderSongFileSummary() {
      const file = songInput.files[0];
      if (!file) {
        songFileSummary.innerHTML = "";
        return;
      }
      songFileSummary.innerHTML = `
        <div class="selected-file-row">
          <span class="selected-file-name">${escapeHtml(file.name)}</span>
          <button class="danger file-remove" id="clearSongButton" type="button">取消</button>
        </div>
      `;
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

    function selectedEngine() {
      const checked = form.querySelector('input[name="engine_id"]:checked');
      return checked ? checked.value : "seedvc";
    }

    async function refreshVoiceModels() {
      const engine = selectedEngine();
      const showTraining = engine === "rvc_applio" && Boolean(voiceProfile.value);
      applioTrainPanel.classList.toggle("visible", showTraining);
      if (engine !== "rvc_applio" && engine !== "rvc_mlx") {
        voiceModel.innerHTML = '<option value="">Seed-VC 默认参考音色</option>';
        voiceModel.disabled = true;
        voiceModelHint.textContent = "Seed-VC 会直接使用当前音色参考音频";
        applioTrainMessage.textContent = "";
        return;
      }
      voiceModel.disabled = false;
      if (!voiceProfile.value) {
        voiceModel.innerHTML = '<option value="">先选择已保存音色</option>';
        voiceModelHint.textContent = "Applio RVC 需要已保存音色和已训练模型";
        applioTrainMessage.textContent = "";
        return;
      }
      voiceModel.innerHTML = '<option value="">加载模型中...</option>';
      try {
        const response = await fetch(`/api/voice-models?voice_id=${encodeURIComponent(voiceProfile.value)}&engine_id=${encodeURIComponent(engine)}`);
        const data = await response.json();
        const readyModels = (data.models || []).filter((model) => model.status === "ready");
        if (!readyModels.length) {
          voiceModel.innerHTML = '<option value="">没有可用 Applio RVC 模型</option>';
          voiceModelHint.textContent = "该音色还没有 Applio RVC 模型，请先添加素材并训练";
          return;
        }
        voiceModel.innerHTML = '<option value="">自动选择最新模型</option>' + readyModels.map((model) => {
          const seconds = model.dataset_seconds == null ? "" : ` · ${formatNumber(model.dataset_seconds, 0)}秒素材`;
          return `<option value="${escapeHtml(model.id)}">${escapeHtml(model.name)}${seconds}</option>`;
        }).join("");
        voiceModelHint.textContent = `可用模型 ${readyModels.length} 个`;
      } catch (error) {
        voiceModel.innerHTML = '<option value="">模型加载失败</option>';
        voiceModelHint.textContent = error.message;
      }
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
      refreshVoiceModels();
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
      if (!songInput.files.length) {
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

    async function runApplioAction(kind) {
      const id = voiceProfile.value;
      if (!id) {
        applioTrainMessage.className = "message error";
        applioTrainMessage.textContent = "先选择一个已保存音色";
        return;
      }
      const isTrain = kind === "train";
      const button = isTrain ? trainApplioButton : prepareApplioButton;
      const endpoint = isTrain ? "/api/applio-train" : "/api/applio-prepare";
      applioTrainMessage.className = "message";
      applioTrainMessage.textContent = isTrain ? "训练中..." : "准备数据集中...";
      prepareApplioButton.disabled = true;
      trainApplioButton.disabled = true;
      startProgressPolling();
      try {
        const body = new FormData();
        body.append("voice_profile_id", id);
        const response = await fetch(endpoint, { method: "POST", body });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || (isTrain ? "训练失败" : "准备失败"));
        }
        if (isTrain) {
          applioTrainMessage.textContent = `训练完成：${data.name || data.id}`;
          await refreshVoiceModels();
          if (data.id) voiceModel.value = data.id;
        } else {
          const seconds = data.total_seconds == null ? "-" : `${formatNumber(data.total_seconds, 0)}秒`;
          const warnings = Array.isArray(data.warnings) && data.warnings.length ? `；${data.warnings.join("；")}` : "";
          applioTrainMessage.textContent = `数据集已准备：${seconds}素材${warnings}`;
        }
      } catch (error) {
        applioTrainMessage.className = "message error";
        applioTrainMessage.textContent = error.message;
      } finally {
        prepareApplioButton.disabled = false;
        trainApplioButton.disabled = false;
        stopProgressPolling();
      }
    }

    prepareApplioButton.addEventListener("click", () => runApplioAction("prepare"));
    trainApplioButton.addEventListener("click", () => runApplioAction("train"));

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
    voiceFileList.addEventListener("click", (event) => {
      const removeButton = event.target.closest(".file-remove");
      if (!removeButton) return;
      removeVoiceFile(Number(removeButton.dataset.index));
    });
    songInput.addEventListener("change", renderSongFileSummary);
    songFileSummary.addEventListener("click", (event) => {
      if (!event.target.closest("#clearSongButton")) return;
      songInput.value = "";
      renderSongFileSummary();
    });
    voiceProfile.addEventListener("change", syncLibraryControls);
    Array.from(form.elements["engine_id"]).forEach((input) => {
      input.addEventListener("change", syncLibraryControls);
    });
    renderVoiceFileSummary();
    renderSongFileSummary();
    syncLibraryControls();
  </script>
</body>
</html>"""
    return body.replace("__VOICE_OPTIONS__", voice_options)
