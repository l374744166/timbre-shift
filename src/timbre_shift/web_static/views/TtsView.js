import { api } from '../api.js';
import { qs } from '../utils.js';
import { ResultCard } from '../components/ResultCard.js';
import { renderResult } from './DashboardView.js';

function voiceOptions() {
  return qs('#voiceProfile').innerHTML;
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
      <label>TTS 声音<select id="ttsVoice" name="tts_voice"><option value="Tingting">中文女声 Tingting</option><option value="Eddy (中文（中国大陆）)">中文男声 Eddy</option><option value="Flo (中文（中国大陆）)">中文女声 Flo</option><option value="Meijia">中文女声 Meijia</option></select></label>
    </div></section>
    <section class="step-section"><h3>3. 输入朗读文字</h3><textarea id="ttsText" name="tts_text" rows="7" placeholder="请输入要朗读的文字，例如：大家好，欢迎体验 Timbre Shift 本地 AI 音色转换工作台。"></textarea><p class="muted">当前优先使用 Piper 中文模型；模型缺失时自动用本机系统 TTS 保底。</p></section>
    <section class="step-section"><h3>4. 朗读设置</h3><div class="settings-grid">
      <label>生成目标<select name="rvc_preset"><option value="stable_balanced">自然稳定</option><option value="clear_diction">字更清楚</option><option value="stronger_timbre_safe">更像目标音色</option></select></label>
      <label>人声修饰<select name="vocal_style"><option value="neutral">不额外修饰</option><option value="close_intimate">贴脸清晰</option><option value="narrative_soft">柔和叙述</option><option value="low_thick">温暖厚实</option><option value="bright_pop">明亮一点</option></select></label>
      <label>朗读速度<select name="tts_rate"><option value="0">正常</option><option value="-20">慢一点</option><option value="20">快一点</option></select></label>
    </div><input type="hidden" name="mode" value="m2max_hq_30"><input type="hidden" name="tts_provider" value="auto"><input type="hidden" name="diction_mode" value="off"></section>
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
    engineInputs.forEach((input) => input.addEventListener('change', () => { syncCards(); loadModels().catch(() => {}); }));
    qs('#ttsVoiceProfile').addEventListener('change', () => loadModels().catch(() => {}));
    syncCards();
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
