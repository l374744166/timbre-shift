import { api } from '../api.js';
import { state, setSelectedEngine } from '../state.js';
import { qs, qsa, escapeHtml, formatNumber } from '../utils.js';
import { navigate } from '../router.js';
import { VoiceCard } from '../components/VoiceCard.js';
import { SongCard } from '../components/SongCard.js';
import { ProgressSteps } from '../components/ProgressSteps.js';
import { ResultCard } from '../components/ResultCard.js';
import { VariantCard } from '../components/VariantCard.js';

function isRvc() {
  return state.selectedEngine === 'rvc_applio';
}

function voiceCards() {
  const select = qs('#voiceProfile');
  const empty = isRvc() ? '还没有 RVC 音色库，先创建音色，再添加训练素材。' : '还没有参考声音，先上传一段清晰声音。';
  return Array.from(select.options).filter((option) => option.value).map((option) => VoiceCard(option, state.selectedVoiceId, state.selectedEngine)).join('') || `<div class="empty-state">${empty}</div>`;
}
function songCards() {
  const select = qs('#songLibrary');
  return Array.from(select.options).filter((option) => option.value).map((option) => SongCard(option, state.selectedSongId)).join('') || '<div class="empty-state">还没有歌曲库记录，可以直接上传新歌曲。</div>';
}

function formatSeconds(value) {
  if (value === null || value === undefined || value === '') return '-';
  const seconds = Number(value);
  if (Number.isNaN(seconds)) return '-';
  if (seconds < 60) return `${Math.round(seconds)} 秒`;
  return `${Math.round(seconds / 60)} 分 ${Math.round(seconds % 60)} 秒`;
}

function formatDate(value) {
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '-' : date.toLocaleString('zh-CN', { hour12: false });
}

function labelFromMap(value, labels) {
  return labels[value] || value || '-';
}

function resultFacts(data) {
  const metrics = data.metrics || {};
  const facts = [
    ['引擎', data.engine_id === 'rvc_applio' ? 'Applio RVC' : (data.engine_id === 'seedvc' ? 'Seed-VC' : data.engine_id || '-')],
    ['目标音色', metrics.voice_profile_name || '-'],
    ['歌曲', metrics.song_title || '上传歌曲'],
    ['生成目标', labelFromMap(metrics.rvc_preset, { stable_balanced: '自然稳定', clear_diction: '歌词更清楚', stronger_timbre_safe: '更像目标音色' })],
    ['人声修饰', labelFromMap(metrics.vocal_style, { neutral: '不额外修饰', close_intimate: '贴脸清晰', narrative_soft: '柔和抒情', low_thick: '温暖厚实', bright_pop: '明亮流行' })],
    ['混音风格', labelFromMap(metrics.mix_style, { natural: '自然', vocal_forward: '人声靠前', blend_with_backing: '融进伴奏' })],
    ['总用时', `${formatNumber(metrics.total_seconds, 1)} 秒`],
  ];
  return facts.map(([label, value]) => `<div class="result-fact"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join('');
}

function resultNotices(data) {
  const diagnostics = data.metrics?.diagnostics || {};
  const issue = diagnostics.most_likely_issue;
  const suggestions = Array.isArray(diagnostics.suggestions) ? diagnostics.suggestions : [];
  const notices = [];
  if (issue && issue !== '未发现明显异常') notices.push(['问题提示', issue]);
  suggestions.slice(0, 2).forEach((text) => notices.push(['建议', text]));
  if (data.dry_vocal_download_wav_url || data.dry_vocal_download_mp3_url) notices.push(['干声输出', '已生成，可单独试听目标人声。']);
  return notices.map(([label, text]) => `<div class="result-notice"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(text)}</span></div>`).join('');
}

function scoreItems(items) {
  return (items || []).map((item) => `<div class="score-item"><strong>${escapeHtml(item.label)}</strong><b>${escapeHtml(item.status || item.value || '-')}</b><span>${escapeHtml(item.detail || '')}</span></div>`).join('');
}

function rvcTrainingPanel() {
  if (!isRvc()) return '';
  return `<section class="step-section rvc-inline-panel" id="rvcInlinePanel">
    <div class="section-head-row"><div><h3>RVC 训练和模型</h3><p class="muted">选中音色后，这里直接看素材、模型和训练状态，不用跳来跳去。</p></div><button class="secondary" id="openTrainingPageButton" type="button">打开完整训练页</button></div>
    <div class="train-flow">
      <div class="step-card wide"><strong>训练素材</strong><div id="dashboardSampleList" class="sample-list">先选择一个 RVC 音色库</div></div>
      <div class="step-card wide"><strong>已训练模型</strong><div id="dashboardModelList" class="sample-list">先选择一个 RVC 音色库</div></div>
      <div class="step-card"><strong>一键训练</strong><select id="dashboardApplioEpochs"><option value="10">10 轮</option><option value="40">40 轮</option><option value="80">80 轮</option></select><button id="dashboardTrainApplioButton" type="button">准备并训练</button><span class="muted">会自动准备数据集</span></div>
      <div class="step-card wide"><strong>训练状态</strong><div id="dashboardTrainMessage" class="message">选择音色后可直接训练；生成时会自动使用可用模型，也可以手动选择模型。</div></div>
    </div>
  </section>`;
}

function sampleRow(sample) {
  return `<div class="sample-row" data-sample-id="${escapeHtml(sample.id)}">
    <div><strong>${escapeHtml(sample.name || '训练素材')}</strong><span>${escapeHtml(sample.source_label || '-')} · ${formatSeconds(sample.duration_seconds)}</span></div>
    <button class="secondary sample-delete" data-id="${escapeHtml(sample.id)}" type="button">删除</button>
  </div>`;
}

function modelRow(model) {
  const epochs = model.epochs ? `${model.epochs} 轮` : '轮数未知';
  const status = model.status === 'ready' ? '可用' : model.status || '-';
  const selected = model.id === state.selectedVoiceModelId;
  return `<div class="model-row ${selected ? 'selected' : ''}" data-model-id="${escapeHtml(model.id)}">
    <div>
      <strong>${escapeHtml(model.name || 'RVC 模型')}</strong>
      <span>${status} · ${epochs} · 训练素材 ${formatSeconds(model.dataset_seconds)} · 训练用时 ${formatSeconds(model.training_seconds)}</span>
      <span>更新时间：${formatDate(model.updated_at)}</span>
    </div>
    <div class="button-row"><button class="secondary model-pick" data-id="${escapeHtml(model.id)}" type="button">选择</button><button class="secondary model-delete" data-id="${escapeHtml(model.id)}" type="button">删除</button></div>
  </div>`;
}


function selectedVoiceSampleCount() {
  const option = qs('#voiceProfile')?.querySelector(`option[value="${CSS.escape(state.selectedVoiceId)}"]`);
  return Number(option?.dataset.sampleCount || 0);
}

function validateBeforeGenerate() {
  const hasUploadedVoice = Boolean(qs('#voice')?.files?.length);
  const hasUploadedSong = Boolean(qs('#song')?.files?.length);
  if (!state.selectedVoiceId && !hasUploadedVoice) {
    return isRvc() ? '请先选择一个 RVC 音色库，或先去音色库创建。' : '请先选择参考声音，或上传一段新的参考声音。';
  }
  if (!isRvc() && state.selectedVoiceId && selectedVoiceSampleCount() <= 0 && !hasUploadedVoice) {
    return '你现在是 Seed-VC 快速试听，但选中的音色库还没有参考声音。请上传参考声音，或切到 RVC 正式生成。';
  }
  if (!state.selectedSongId && !hasUploadedSong) {
    return '请先选择歌曲库里的歌曲，或上传一个新歌曲文件。';
  }
  return '';
}

function engineCopy() {
  if (isRvc()) {
    return {
      steps: ['RVC模式', '训练音色', '歌曲', '正式生成'],
      badge: 'RVC 正式生成',
      intro: 'RVC 需要先有训练素材和模型，适合长期复用同一个目标音色。',
      voiceTitle: 'Step 2：选择 RVC 音色库 / 已训练模型',
      voiceHelp: '这里选的是要训练或已经训练过的音色库，不是临时参考音频。',
      voiceNamePlaceholder: 'RVC 音色库名称',
      sourceLabel: '训练素材类型',
      saveButton: '创建 RVC 音色库',
      addButton: '添加训练素材',
      songHelp: 'RVC 会把歌曲人声换成已训练音色，建议源歌人声越干净越好。',
      goalLabel: 'RVC 生成目标',
      styleLabel: 'RVC 人声修饰',
      outputLabel: '正式输出',
      submit: '开始 RVC 生成',
      advancedTitle: 'RVC 高级设置',
      goalOptions: [
        ['stable_balanced', '自然稳定'],
        ['clear_diction', '歌词更清楚'],
        ['stronger_timbre_safe', '更像目标音色'],
      ],
      styleOptions: [
        ['neutral', '不额外修饰'],
        ['close_intimate', '贴脸清晰'],
        ['narrative_soft', '柔和抒情'],
        ['low_thick', '温暖厚实'],
        ['bright_pop', '明亮流行'],
      ],
    };
  }
  return {
    steps: ['Seed-VC模式', '参考声音', '歌曲', '快速试听'],
    badge: 'Seed-VC 快速试听',
    intro: 'Seed-VC 用短参考声音快速听效果，不训练模型，适合先判断音色方向。',
    voiceTitle: 'Step 2：选择 Seed-VC 参考声音',
    voiceHelp: '这里选的是临时参考声音，通常准备 15-30 秒清晰干声即可。',
    voiceNamePlaceholder: '参考声音名称',
    sourceLabel: '参考声音类型',
    saveButton: '保存参考声音',
    addButton: '补充参考素材',
    songHelp: 'Seed-VC 更适合先做短片段试听，确认方向后再走 RVC 训练。',
    goalLabel: '试听目标',
    styleLabel: '试听修饰',
    outputLabel: '试听输出',
    submit: '开始 Seed-VC 试听',
    advancedTitle: 'Seed-VC 高级设置',
    goalOptions: [
      ['stable_balanced', '快速稳定'],
      ['clear_diction', '歌词清楚'],
      ['stronger_timbre_safe', '更贴近参考声音'],
    ],
    styleOptions: [
      ['neutral', '不额外修饰'],
      ['close_intimate', '人声更清晰'],
      ['narrative_soft', '柔和一点'],
      ['low_thick', '温暖厚一点'],
      ['bright_pop', '明亮一点'],
    ],
  };
}

export const DashboardView = {
  render: () => {
    const copy = engineCopy();
    const voiceSourceControl = `<select id="voiceSourceType" name="voice_source_type" aria-label="${copy.sourceLabel}"><option value="clean_voice">干净人声</option><option value="mixed_voice">带伴奏，自动分离人声</option></select>`;
    const uploadStripClass = 'upload-strip voice-upload-strip';
    return `<form id="form" class="dashboard-form">
    <section class="view-panel"><div class="view-head"><div><h2>工作台</h2><p>${copy.intro}</p></div><span class="status-badge ok">${copy.badge}</span></div>${ProgressSteps(copy.steps, 0)}</section>
    <section class="step-section"><h3>Step 1：选择转换方式</h3><div class="choice-grid engine-choice-grid">
      <label class="choice-card ${state.selectedEngine === 'seedvc' ? 'selected' : ''}"><input type="radio" name="engine_id" value="seedvc" ${state.selectedEngine === 'seedvc' ? 'checked' : ''}><strong>Seed-VC 快速试听</strong><span>参考声音即用，不训练模型，适合先听方向</span></label>
      <label class="choice-card ${state.selectedEngine === 'rvc_applio' ? 'selected' : ''}"><input type="radio" name="engine_id" value="rvc_applio" ${state.selectedEngine === 'rvc_applio' ? 'checked' : ''}><strong>Applio RVC 正式生成</strong><span>先训练目标音色模型，适合多首歌长期复用</span></label>
    </div></section>
    <section class="step-section"><h3>${copy.voiceTitle}</h3><p class="muted">${copy.voiceHelp}</p><div class="resource-grid" id="voiceCards">${voiceCards()}</div>
      <div class="${uploadStripClass}"><input id="voice" name="voice" type="file" accept="audio/*" multiple><input id="voiceName" name="voice_name" placeholder="${copy.voiceNamePlaceholder}">${voiceSourceControl}<button class="secondary" id="saveVoiceButton" type="button">${copy.saveButton}</button><button class="secondary" id="addVoiceSampleButton" type="button">${copy.addButton}</button>${isRvc() ? '<button id="addVoiceSampleAndTrainButton" type="button">添加素材并训练</button>' : ''}</div><div class="message" id="voiceSaveMessage"></div></section>
    ${rvcTrainingPanel()}
    <section class="step-section"><h3>Step 3：选择歌曲</h3><p class="muted">${copy.songHelp}</p><div class="resource-grid" id="songCards">${songCards()}</div><div class="upload-strip"><input id="song" name="song" type="file" accept="audio/*"><span class="muted">也可以上传干净人声，高级设置里选择源人声清理。</span></div></section>
    <section class="step-section"><h3>Step 4：生成设置</h3><div class="settings-grid">
      <label>${copy.goalLabel}<select id="rvcPreset" name="rvc_preset">${copy.goalOptions.map(([value, label]) => `<option value="${value}">${label}</option>`).join('')}</select></label>
      <label>${copy.styleLabel}<select id="vocalStyle" name="vocal_style">${copy.styleOptions.map(([value, label]) => `<option value="${value}">${label}</option>`).join('')}</select></label>
      <label>${copy.outputLabel}<select id="outputMode"><option value="full">完整歌曲</option><option value="dry">干声</option><option value="variants">生成对比版本</option></select></label>
    </div>
    <details class="details-panel"><summary>${copy.advancedTitle}</summary><div class="settings-grid"><label>源人声清理<select id="preRvcCleanupMode" name="pre_rvc_cleanup_mode"><option value="off">关闭</option><option value="standard">标准</option><option value="strong">强力</option></select></label><label>混音风格<select id="mixStyle" name="mix_style"><option value="natural">自然</option><option value="vocal_forward">人声靠前</option><option value="blend_with_backing">融进伴奏</option></select></label>${isRvc() ? '<label>咬字增强<select id="dictionMode" name="diction_mode"><option value="off">关闭</option><option value="light" selected>轻微</option><option value="medium">中等</option><option value="strong">强</option></select></label><label>音色记忆库<select id="rvcIndexRate" name="rvc_index_rate"><option value="0">关闭</option><option value="0.25">轻度</option><option value="0.45">中度</option></select></label><label class="check"><input id="allowExperimentalIndex" name="allow_experimental_index" type="checkbox">开启实验音色记忆库</label>' : '<input type="hidden" name="diction_mode" value="off"><input type="hidden" name="rvc_index_rate" value="0">'}</div></details>
    <input type="hidden" name="mode" value="m2max_hq_30"><input type="hidden" id="voiceModel" name="voice_model_id"><input type="hidden" name="song_id" id="songIdField"><input type="hidden" name="voice_profile_id" id="voiceIdField"><input type="hidden" name="mix_style" value="natural"><input type="hidden" id="generateVariants" name="generate_variants" value="">
    <div class="action-bar"><button id="submit" type="submit">${copy.submit}</button><div id="message" class="message"></div></div></section>
    <section class="task-panel">
      <div class="section-head-row"><div><h3>当前任务</h3><p class="muted">生成进度和完成用时</p></div><span id="progressStatus" class="status-badge">待命</span></div>
      <div class="progress-card">
        <div class="progress-meta"><span id="progressStep">待命</span><span id="progressTime">00:00</span></div>
        <div class="progress-track"><div id="progressBar" class="progress-bar"></div></div>
      </div>
    </section>
    ${ResultCard()}</form>`;
  },
  mount: () => {
    const selectVoice = (id) => {
      state.selectedVoiceId = id || '';
      qs('#voiceProfile').value = state.selectedVoiceId;
      qs('#voiceIdField').value = state.selectedVoiceId;
      qs('#voiceCards').innerHTML = voiceCards();
    };
    const upsertVoiceOption = (data) => {
      if (!data?.id) return;
      const select = qs('#voiceProfile');
      let option = select.querySelector(`option[value="${CSS.escape(data.id)}"]`);
      if (!option) {
        option = document.createElement('option');
        option.value = data.id;
        select.appendChild(option);
      }
      option.textContent = data.name || qs('#voiceName').value || '未命名音色';
      option.dataset.sampleCount = String(data.sample_count ?? option.dataset.sampleCount ?? 0);
      option.dataset.rvcModelCount = String(data.rvc_model_count ?? option.dataset.rvcModelCount ?? 0);
    };
    const updateSelectedVoiceStats = ({ sampleCount, modelCount } = {}) => {
      const option = qs('#voiceProfile')?.querySelector(`option[value="${CSS.escape(state.selectedVoiceId)}"]`);
      if (option && sampleCount != null) option.dataset.sampleCount = String(sampleCount);
      if (option && modelCount != null) option.dataset.rvcModelCount = String(modelCount);
      qs('#voiceCards').innerHTML = voiceCards();
    };
    const removeVoiceOption = (id) => {
      const option = qs('#voiceProfile')?.querySelector(`option[value="${CSS.escape(id)}"]`);
      option?.remove();
      if (state.selectedVoiceId === id) {
        state.selectedVoiceId = '';
        qs('#voiceProfile').value = '';
        qs('#voiceIdField').value = '';
      }
      qs('#voiceCards').innerHTML = voiceCards();
    };
    const removeSongOption = (id) => {
      const option = qs('#songLibrary')?.querySelector(`option[value="${CSS.escape(id)}"]`);
      option?.remove();
      if (state.selectedSongId === id) {
        state.selectedSongId = '';
        qs('#songLibrary').value = '';
        qs('#songIdField').value = '';
      }
      qs('#songCards').innerHTML = songCards();
    };
    const setDashboardMessage = (text, isError = false) => {
      const message = qs('#dashboardTrainMessage');
      if (!message) return;
      message.className = `message${isError ? ' error' : ''}`;
      message.textContent = text;
    };
    const loadRvcTrainingDetails = async () => {
      if (!isRvc() || !qs('#rvcInlinePanel')) return;
      if (!state.selectedVoiceId) {
        qs('#dashboardSampleList').innerHTML = '<div class="muted">先选择一个 RVC 音色库</div>';
        qs('#dashboardModelList').innerHTML = '<div class="muted">先选择一个 RVC 音色库</div>';
        return;
      }
      try {
        const [samplesData, modelsData] = await Promise.all([
          api.voiceSamples(state.selectedVoiceId),
          api.voiceModels(state.selectedVoiceId, 'rvc_applio'),
        ]);
        const samples = samplesData.samples || [];
        const models = modelsData.models || [];
        qs('#dashboardSampleList').innerHTML = samples.map(sampleRow).join('') || '<div class="muted">暂无训练素材，可以在上面上传后点“添加训练素材”</div>';
        qs('#dashboardModelList').innerHTML = models.map(modelRow).join('') || '<div class="muted">暂无已训练模型，点“准备并训练”即可一键完成</div>';
        updateSelectedVoiceStats({ sampleCount: samples.length, modelCount: models.filter((model) => model.status === 'ready').length });
      } catch (error) {
        setDashboardMessage(error.message, true);
      }
    };
    qsa('input[name="engine_id"]').forEach((input) => input.addEventListener('change', () => { setSelectedEngine(input.value); navigate('dashboard'); }));
    if (state.selectedVoiceId) {
      const option = qs('#voiceProfile')?.querySelector(`option[value="${CSS.escape(state.selectedVoiceId)}"]`);
      if (option) selectVoice(state.selectedVoiceId);
    }
    qs('#voiceCards')?.addEventListener('click', async (event) => {
      const deleteButton = event.target.closest('.voice-delete');
      if (deleteButton) {
        const name = deleteButton.dataset.name || '这个音色';
        if (!window.confirm(`删除音色「${name}」？`)) return;
        qs('#voiceSaveMessage').textContent = '正在删除音色...';
        const body = new FormData();
        body.append('voice_profile_id', deleteButton.dataset.id || '');
        try {
          const data = await api.post('/api/delete-voice', body);
          removeVoiceOption(data.id || deleteButton.dataset.id || '');
          qs('#voiceSaveMessage').textContent = data.message || '音色已删除';
          await loadRvcTrainingDetails();
        } catch (error) {
          qs('#voiceSaveMessage').textContent = error.message;
        }
        return;
      }
      const button = event.target.closest('.voice-select,.voice-train');
      if (!button) return;
      selectVoice(button.dataset.id);
      await loadRvcTrainingDetails();
      if (button.classList.contains('voice-train')) qs('#rvcInlinePanel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    qs('#songCards')?.addEventListener('click', async (event) => { const deleteButton = event.target.closest('.song-delete'); if (deleteButton) { const name = deleteButton.dataset.name || '这首歌'; if (!window.confirm(`删除歌曲「${name}」？`)) return; qs('#message').textContent = '正在删除歌曲...'; const body = new FormData(); body.append('song_id', deleteButton.dataset.id || ''); try { const data = await api.post('/api/delete-song', body); removeSongOption(data.id || deleteButton.dataset.id || ''); qs('#message').textContent = data.message || '歌曲已删除'; } catch (error) { qs('#message').textContent = error.message; } return; } const button = event.target.closest('.song-select'); if (!button) return; state.selectedSongId = button.dataset.id; qs('#songLibrary').value = state.selectedSongId; qs('#songIdField').value = state.selectedSongId; navigate('dashboard'); });
    qs('#outputMode')?.addEventListener('change', (event) => { qs('#generateVariants').value = event.target.value === 'variants' ? 'on' : ''; });
    qs('#saveVoiceButton')?.addEventListener('click', async () => { const body = new FormData(); const files = qs('#voice').files; Array.from(files).forEach((file) => body.append('voice', file)); body.append('voice_name', qs('#voiceName').value || '未命名音色'); const sourceType = qs('#voiceSourceType')?.value || 'clean_voice'; body.append('voice_source_type', sourceType); qs('#voiceSaveMessage').textContent = sourceType === 'mixed_voice' ? '正在分离人声并保存...' : (isRvc() ? '正在创建 RVC 音色库...' : '正在保存参考声音...'); try { const data = await api.post(isRvc() ? '/api/create-voice-profile' : '/api/save-voice', body); upsertVoiceOption(data); selectVoice(data.id); qs('#voiceSaveMessage').textContent = data.message || '已保存'; await loadRvcTrainingDetails(); } catch (error) { qs('#voiceSaveMessage').textContent = error.message; } });
    const addVoiceSample = async ({ trainAfter = false } = {}) => {
      if (!state.selectedVoiceId) {
        qs('#voiceSaveMessage').textContent = '先选择或创建一个 RVC 音色库';
        return false;
      }
      const body = new FormData();
      Array.from(qs('#voice').files).forEach((file) => body.append('voice', file));
      body.append('voice_name', qs('#voiceName').value || '声音素材');
      body.append('voice_profile_id', state.selectedVoiceId);
      const sourceType = qs('#voiceSourceType')?.value || 'clean_voice';
      body.append('voice_source_type', sourceType);
      qs('#voiceSaveMessage').textContent = sourceType === 'mixed_voice'
        ? (trainAfter ? '正在分离人声，完成后会自动开始训练...' : '正在分离人声并添加素材...')
        : (trainAfter ? '正在添加训练素材，完成后会自动开始训练...' : (isRvc() ? '正在添加训练素材...' : '正在补充参考素材...'));
      try {
        const data = await api.post('/api/add-voice-sample', body);
        updateSelectedVoiceStats({ sampleCount: data.sample_count });
        qs('#voiceSaveMessage').textContent = data.message || '素材已添加';
        await loadRvcTrainingDetails();
        return true;
      } catch (error) {
        qs('#voiceSaveMessage').textContent = error.message;
        return false;
      }
    };
    const trainSelectedRvc = async ({ prefix = '正在准备数据集并训练...' } = {}) => {
      if (!state.selectedVoiceId) {
        setDashboardMessage('先选择一个 RVC 音色库', true);
        return null;
      }
      const body = new FormData();
      body.append('voice_profile_id', state.selectedVoiceId);
      body.append('epochs', qs('#dashboardApplioEpochs').value);
      setDashboardMessage(prefix);
      try {
        const data = await api.post('/api/applio-train', body);
        setDashboardMessage(`${data.message || '模型已保存'} · ${qs('#dashboardApplioEpochs').value} 轮 · 用时 ${formatSeconds(data.training_seconds)}`);
        if (data.id) {
          state.selectedVoiceModelId = data.id;
          qs('#voiceModel').value = data.id;
        }
        await loadRvcTrainingDetails();
        return data;
      } catch (error) {
        setDashboardMessage(error.message, true);
        return null;
      }
    };
    qs('#addVoiceSampleButton')?.addEventListener('click', async () => { await addVoiceSample(); });
    qs('#addVoiceSampleAndTrainButton')?.addEventListener('click', async () => { const added = await addVoiceSample({ trainAfter: true }); if (added) await trainSelectedRvc({ prefix: `素材已添加，正在准备数据集并训练 ${qs('#dashboardApplioEpochs').value} 轮...` }); });
    qs('#openTrainingPageButton')?.addEventListener('click', () => navigate('training'));
    qs('#dashboardTrainApplioButton')?.addEventListener('click', async () => { await trainSelectedRvc(); });
    qs('#dashboardSampleList')?.addEventListener('click', async (event) => { const button = event.target.closest('.sample-delete'); if (!button) return; if (!window.confirm('确定删除这个训练素材吗？')) return; const body = new FormData(); body.append('voice_profile_id', state.selectedVoiceId); body.append('sample_id', button.dataset.id || ''); setDashboardMessage('正在删除素材...'); try { const data = await api.post('/api/delete-voice-sample', body); setDashboardMessage(data.message || '素材已删除'); updateSelectedVoiceStats({ sampleCount: data.sample_count }); await loadRvcTrainingDetails(); } catch (error) { setDashboardMessage(error.message, true); } });
    qs('#dashboardModelList')?.addEventListener('click', async (event) => { const pick = event.target.closest('.model-pick'); const del = event.target.closest('.model-delete'); if (pick) { state.selectedVoiceModelId = pick.dataset.id || ''; qs('#voiceModel').value = state.selectedVoiceModelId; setDashboardMessage('已选择这个 RVC 模型用于生成'); await loadRvcTrainingDetails(); return; } if (!del) return; if (!window.confirm('确定删除这个 RVC 模型吗？')) return; const body = new FormData(); body.append('voice_model_id', del.dataset.id || ''); setDashboardMessage('正在删除模型...'); try { const data = await api.post('/api/delete-voice-model', body); if (state.selectedVoiceModelId === data.id) { state.selectedVoiceModelId = ''; qs('#voiceModel').value = ''; } setDashboardMessage(data.message || '模型已删除'); await loadRvcTrainingDetails(); } catch (error) { setDashboardMessage(error.message, true); } });
    qs('#savePreferenceButton')?.addEventListener('click', async () => { const body = new FormData(qs('#form')); body.set('engine_id', state.selectedEngine); body.set('voice_profile_id', state.selectedVoiceId); qs('#message').textContent = '正在保存默认参数...'; try { const data = await api.post('/api/voice-preference', body); qs('#message').textContent = data.message || '已保存默认参数'; } catch (error) { qs('#message').textContent = error.message; } });
    qs('#variants')?.addEventListener('click', async (event) => { const button = event.target.closest('.variant-select,.variant-feedback'); if (!button) return; const body = new FormData(); body.append('variant_id', button.dataset.id || ''); const isSelect = button.classList.contains('variant-select'); qs('#message').textContent = isSelect ? '正在设为最终版本...' : '正在标记喜欢...'; try { const data = await api.post(isSelect ? '/api/select-variant' : '/api/variant-feedback', body); if (isSelect) { if (data.download_mp3_url) { qs('#player').src = `${data.download_mp3_url}?t=${Date.now()}`; qs('#download').href = data.download_mp3_url; } if (data.download_wav_url) qs('#downloadWav').href = data.download_wav_url; } qs('#message').textContent = data.message || '已完成'; } catch (error) { qs('#message').textContent = error.message; } });
    qs('#form').addEventListener('submit', async (event) => { event.preventDefault(); const validation = validateBeforeGenerate(); if (validation) { qs('#message').textContent = validation; return; } qs('#message').textContent = isRvc() ? '正在 RVC 正式生成...' : '正在 Seed-VC 快速试听...'; const body = new FormData(qs('#form')); body.set('engine_id', state.selectedEngine); body.set('voice_profile_id', state.selectedVoiceId); body.set('song_id', state.selectedSongId); try { const data = await api.generate(body); renderResult(data); qs('#message').textContent = data.message || '生成完成'; } catch (error) { qs('#message').textContent = error.message; } });
    loadRvcTrainingDetails();
  },
};

export function renderResult(data) {
  state.lastResult = data;
  const result = qs('#result');
  result.classList.remove('hidden');
  qs('#resultSummary').textContent = `${data.message || '生成完成'} · ${formatNumber(data.metrics?.total_seconds, 1)} 秒`;
  qs('#resultFacts').innerHTML = resultFacts(data);
  const isTtsResult = data.metrics?.source_mode === 'tts_clean_vocal' || Boolean(data.tts);
  result.classList.toggle('tts-result', isTtsResult);
  qs('#resultGrid')?.classList.toggle('single-result-grid', isTtsResult);
  if (qs('#mainPlayerTitle')) qs('#mainPlayerTitle').textContent = isTtsResult ? '朗读结果' : '成品歌曲';
  qs('#dryVocalCard')?.classList.toggle('hidden', isTtsResult);
  const mp3 = data.download_mp3_url || data.download_url;
  const wav = data.download_wav_url || data.download_url;
  qs('#player').src = mp3 ? `${mp3}?t=${Date.now()}` : '';
  qs('#download').href = mp3 || '#';
  qs('#download').download = data.mp3_filename || 'final.mp3';
  qs('#downloadWav').href = wav || '#';
  qs('#downloadWav').download = data.wav_filename || 'final.wav';
  qs('#dryVocalPlayer').src = data.dry_vocal_download_mp3_url ? `${data.dry_vocal_download_mp3_url}?t=${Date.now()}` : '';
  qs('#downloadDryVocal').href = data.dry_vocal_download_mp3_url || '#';
  qs('#downloadDryVocalWav').href = data.dry_vocal_download_wav_url || '#';
  qs('#scorecard').innerHTML = scoreItems(data.scorecard);
  qs('#resultNotices').innerHTML = resultNotices(data);
  qs('#metrics').textContent = JSON.stringify(data.metrics || {}, null, 2);
  qs('#variants').innerHTML = (data.variants || []).map(VariantCard).join('');
}
