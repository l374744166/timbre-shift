import { api } from '../api.js';
import { qs, qsa } from '../utils.js';
import { ResultCard } from '../components/ResultCard.js';
import { renderResult } from './DashboardView.js';

function voiceOptions() {
  return qs('#voiceProfile').innerHTML;
}

function qsaSafe(selector) {
  return Array.from(qsa(selector));
}

export const TtsView = {
  render: () => `<form id="ttsForm" class="dashboard-form">
    <section class="view-panel"><div class="view-head"><div><h2>文字朗读</h2><p>输入文字，先生成 TTS 朗读干声，再换成你训练好的目标音色。</p></div><span class="status-badge ok">TTS + 换音</span></div></section>
    <section class="step-section"><h3>1. 选择换音方式</h3><div class="choice-grid engine-choice-grid">
      <label class="choice-card selected"><input type="radio" name="engine_id" value="seedvc" checked><strong>Seed-VC 快速朗读</strong><span>不需要 RVC 模型，适合快速演示。</span></label>
      <label class="choice-card"><input type="radio" name="engine_id" value="rvc_applio"><strong>Applio RVC 正式朗读</strong><span>使用已训练 RVC 模型，音色更稳定。</span></label>
    </div></section>
    <section class="step-section"><h3>2. 选择目标音色</h3><div class="settings-grid">
      <label>目标音色<select id="ttsVoiceProfile" name="voice_profile_id">${voiceOptions()}</select></label>
      <label>RVC 模型<select id="ttsVoiceModel" name="voice_model_id"><option value="">自动选择可用模型</option></select></label>
      <label>TTS 引擎<select id="ttsProvider" name="tts_provider"><option value="auto" selected>自动：优先自然中文</option><option value="edge">Edge 在线中文（推荐）</option><option value="piper">Piper 本地离线</option><option value="system">系统中文保底</option></select></label>
      <label id="edgeVoiceLabel">中文底声<select id="edgeVoice" name="edge_voice"><option value="zh-CN-XiaoxiaoNeural" selected>晓晓 · 女声 · 温和自然</option><option value="zh-CN-XiaoyiNeural">晓伊 · 女声 · 轻快</option><option value="zh-CN-YunxiNeural">云希 · 男声 · 年轻自然</option><option value="zh-CN-YunyangNeural">云扬 · 男声 · 稳重播报</option><option value="zh-CN-YunjianNeural">云健 · 男声 · 有力度</option><option value="zh-CN-liaoning-XiaobeiNeural">晓北 · 女声 · 东北口音</option><option value="zh-CN-shaanxi-XiaoniNeural">晓妮 · 女声 · 陕西口音</option></select></label>
      <label id="systemVoiceLabel" class="hidden">系统中文底声（保底）<select id="ttsVoice" name="tts_voice"><option value="Tingting">婷婷 · 中文女声</option><option value="Eddy (中文（中国大陆）)">Eddy · 中文男声</option><option value="Flo (中文（中国大陆）)">Flo · 中文女声</option><option value="Meijia">美佳 · 中文女声</option></select></label>
    </div></section>
    <section class="step-section"><h3>3. 输入朗读文字</h3><textarea id="ttsText" name="tts_text" rows="7" placeholder="请输入要朗读的文字，例如：大家好，欢迎体验 Timbre Shift 本地 AI 音色转换工作台。"></textarea><p class="muted">默认优先使用 Edge 在线中文神经声；如果网络不可用，可以切到 Piper 本地离线或系统中文保底。</p></section>
    <section class="step-section"><h3>4. 朗读设置</h3><div class="settings-grid">
      <label>生成目标<select name="rvc_preset"><option value="stable_balanced">自然稳定</option><option value="clear_diction">字更清楚</option><option value="stronger_timbre_safe">更像目标音色</option></select></label>
      <label id="ttsVocalStyleLabel" class="hidden">RVC 人声修饰<select id="ttsVocalStyle" name="vocal_style" disabled><option value="neutral">不额外修饰</option><option value="close_intimate">贴脸清晰</option><option value="narrative_soft">柔和叙述</option><option value="low_thick">温暖厚实</option><option value="bright_pop">明亮一点</option></select></label>
      <label>语速倍数<select name="tts_speed"><option value="0.75">0.75x 慢速</option><option value="0.9">0.9x 偏慢</option><option value="1.0" selected>1.0x 正常</option><option value="1.25">1.25x 稍快</option><option value="1.5">1.5x 快速</option><option value="2.0">2.0x 很快</option></select></label>
      <label class="edge-control">语调数值 1-100<input name="tts_pitch" type="number" min="1" max="100" step="1" value="50"></label>
      <label class="edge-control">中文音量<select name="edge_volume"><option value="-10">低一点</option><option value="0" selected>正常</option><option value="10">大一点</option></select></label>
      <label class="piper-control hidden">Piper 自然度<select name="tts_noise_scale"><option value="0.45">更稳定</option><option value="0.667" selected>自然</option><option value="0.9">更有变化</option></select></label>
      <label class="piper-control hidden">Piper 节奏变化<select name="tts_noise_w_scale"><option value="0.5">更稳定</option><option value="0.8" selected>自然</option><option value="1.05">更有起伏</option></select></label>
      <label class="piper-control hidden">Piper 句子停顿<select name="tts_sentence_silence"><option value="0.1">短</option><option value="0.25" selected>正常</option><option value="0.5">长</option><option value="0.8">很长</option></select></label>
      <label class="piper-control hidden">Piper 音量<select name="tts_volume"><option value="0.8">低一点</option><option value="1.0" selected>正常</option><option value="1.2">大一点</option><option value="1.4">更大</option></select></label>
    </div><p class="muted">推荐用 Edge 在线中文；语速倍数只控制快慢，语调数值 1-100 单独控制音高，50 为正常。</p><input type="hidden" name="mode" value="m2max_hq_30"><input type="hidden" name="diction_mode" value="off"></section>
    <section class="task-panel"><div class="section-head-row"><div><h3>当前任务</h3><p class="muted">TTS 生成和换音进度</p></div><span id="progressStatus" class="status-badge">待命</span></div><div class="progress-card"><div class="progress-meta"><span id="progressStep">待命</span><span id="progressTime">00:00</span></div><div class="progress-track"><div id="progressBar" class="progress-bar"></div></div></div></section>
    <div class="action-bar"><button id="ttsSubmit" type="submit">生成朗读</button><div id="message" class="message"></div></div>
    ${ResultCard()}
  </form>`,
  mount: () => {
    const form = qs('#ttsForm');
    const engineInputs = Array.from(form.elements.engine_id || []);
    const modelSelect = qs('#ttsVoiceModel');
    const syncCards = () => {
      engineInputs.forEach((input) => input.closest('.choice-card')?.classList.toggle('selected', input.checked));
    };
    const syncEngineControls = () => {
      const isRvc = form.elements.engine_id.value === 'rvc_applio';
      const styleLabel = qs('#ttsVocalStyleLabel');
      const styleSelect = qs('#ttsVocalStyle');
      styleLabel?.classList.toggle('hidden', !isRvc);
      if (styleSelect) {
        styleSelect.disabled = !isRvc;
        if (!isRvc) styleSelect.value = 'neutral';
      }
    };
    const syncTtsProviderControls = () => {
      const provider = qs('#ttsProvider')?.value || 'auto';
      const showPiper = provider === 'piper';
      const showSystem = provider === 'system';
      const showEdge = provider === 'auto' || provider === 'edge';
      qsaSafe('.piper-control').forEach((el) => el.classList.toggle('hidden', !showPiper));
      qsaSafe('.edge-control').forEach((el) => el.classList.toggle('hidden', !showEdge));
      qs('#edgeVoiceLabel')?.classList.toggle('hidden', !showEdge);
      qs('#systemVoiceLabel')?.classList.toggle('hidden', !showSystem);
    };
    const loadModels = async () => {
      const engine = form.elements.engine_id.value;
      if (engine !== 'rvc_applio') {
        modelSelect.innerHTML = '<option value="">Seed-VC 不需要模型</option>';
        return;
      }
      const voiceId = qs('#ttsVoiceProfile').value;
      const data = await api.voiceModels(voiceId, 'rvc_applio');
      const ready = (data.models || []).filter((model) => model.status === 'ready');
      modelSelect.innerHTML = '<option value="">自动选择可用模型</option>' + ready.map((model) => `<option value="${model.id}">${model.name || 'RVC 模型'}</option>`).join('');
    };
    engineInputs.forEach((input) => input.addEventListener('change', () => { syncCards(); syncEngineControls(); loadModels().catch(() => {}); }));
    qs('#ttsVoiceProfile').addEventListener('change', () => loadModels().catch(() => {}));
    qs('#ttsProvider')?.addEventListener('change', syncTtsProviderControls);
    syncCards();
    syncEngineControls();
    syncTtsProviderControls();
    loadModels().catch(() => {});
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      qs('#message').textContent = '正在生成文字朗读...';
      try {
        const data = await api.post('/api/tts-generate', new FormData(form));
        renderResult(data);
        qs('#message').textContent = data.message || '文字朗读生成完成';
      } catch (error) {
        qs('#message').textContent = error.message;
      }
    });
  },
};
