"""HTML shell for the local Timbre Shift web UI."""

from __future__ import annotations

import html

from .library import DEFAULT_DB_PATH, init_library, list_songs, list_voice_models, list_voice_profiles, list_voice_samples


def page_html() -> str:
    init_library(DEFAULT_DB_PATH)
    voice_option_parts = []
    for profile in list_voice_profiles(only_allowed_targets=True, db_path=DEFAULT_DB_PATH):
        sample_count = len(list_voice_samples(profile.id, db_path=DEFAULT_DB_PATH))
        rvc_models = list_voice_models(profile.id, engine_id="rvc_applio", db_path=DEFAULT_DB_PATH)
        ready_model_count = sum(1 for model in rvc_models if model.status == "ready")
        voice_option_parts.append(
            f'<option value="{html.escape(profile.id)}" '
            f'data-source-type="{html.escape(profile.source_type)}" '
            f'data-sample-count="{sample_count}" '
            f'data-rvc-model-count="{ready_model_count}">{html.escape(profile.name)}</option>'
        )
    voice_options = "\n".join(voice_option_parts)
    song_options = "\n".join(
        f'<option value="{html.escape(song.id)}" data-source-kind="{html.escape(song.source_kind)}">{html.escape(song.title)}</option>'
        for song in list_songs(db_path=DEFAULT_DB_PATH)
    )
    body = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Timbre Shift</title>
  <link rel="stylesheet" href="/static/styles/base.css">
  <link rel="stylesheet" href="/static/styles/layout.css">
  <link rel="stylesheet" href="/static/styles/components.css">
  <link rel="stylesheet" href="/static/styles/dashboard.css">
  <link rel="stylesheet" href="/static/styles/library.css">
  <link rel="stylesheet" href="/static/styles/results.css">
</head>
<body>
  <div class="app-shell">
    <header class="topbar">
      <div>
        <h1>Timbre Shift</h1>
        <p>本地 AI 音色转换工作台</p>
      </div>
      <div class="topbar-status">
        <span class="status-pill" id="envStatus">检查环境中...</span>
        <span class="status-pill" id="seedvcStatus">Seed-VC 检查中</span>
        <span class="status-pill" id="applioStatus">Applio RVC 检查中</span>
      </div>
    </header>

    <aside class="sidebar" aria-label="主导航">
      <button class="nav-item active" data-view="dashboard" type="button">工作台</button>
      <button class="nav-item" data-view="tts" type="button">文字朗读</button>
      <button class="nav-item" data-view="voices" type="button">音色库</button>
      <button class="nav-item" data-view="songs" type="button">歌曲库</button>
      <button class="nav-item" data-view="history" type="button">生成历史</button>
      <button class="nav-item" data-view="environment" type="button">环境检查</button>
      <button class="nav-item" data-view="settings" type="button">设置</button>
    </aside>

    <main class="workspace">
      <section id="viewRoot" class="view-root"></section>
    </main>

    <aside class="rightbar">
      <section class="side-panel">
        <h2>最近生成</h2>
        <div id="recentHistoryList" class="mini-list"><div class="muted">暂无记录</div></div>
      </section>
    </aside>
  </div>

  <select id="voiceProfile" name="voice_profile_id" class="sr-only" aria-hidden="true">
    <option value="">上传新声音 / 新建音色库</option>
    __VOICE_OPTIONS__
  </select>
  <select id="songLibrary" name="song_id" class="sr-only" aria-hidden="true">
    <option value="">上传新的待换声歌曲</option>
    __SONG_OPTIONS__
  </select>

  <script type="module" src="/static/app.js"></script>
</body>
</html>"""
    return body.replace("__VOICE_OPTIONS__", voice_options).replace("__SONG_OPTIONS__", song_options)
