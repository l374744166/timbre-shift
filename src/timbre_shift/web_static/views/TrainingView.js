import { api } from '../api.js';
import { state } from '../state.js';
import { escapeHtml, qs } from '../utils.js';

const formatSeconds = (value) => {
  if (value === null || value === undefined || value === '') return '-';
  const seconds = Number(value);
  if (Number.isNaN(seconds)) return '-';
  if (seconds < 60) return `${Math.round(seconds)} 秒`;
  return `${Math.round(seconds / 60)} 分 ${Math.round(seconds % 60)} 秒`;
};

const formatDate = (value) => {
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '-' : date.toLocaleString('zh-CN', { hour12: false });
};

function sampleRow(sample) {
  return `<div class="sample-row" data-sample-id="${sample.id}">
    <div><strong>${escapeHtml(sample.name)}</strong><span>${escapeHtml(sample.source_label)} · ${formatSeconds(sample.duration_seconds)}</span></div>
    <button class="secondary sample-delete" data-id="${escapeHtml(sample.id)}" type="button">删除</button>
  </div>`;
}

function modelRow(model) {
  const epochs = model.epochs ? `${model.epochs} 轮` : '轮数未知';
  const status = model.status === 'ready' ? '可用' : model.status || '-';
  return `<div class="model-row" data-model-id="${model.id}">
    <div>
      <strong>${escapeHtml(model.name || 'RVC 模型')}</strong>
      <span>${status} · ${epochs} · 训练素材 ${formatSeconds(model.dataset_seconds)} · 训练用时 ${formatSeconds(model.training_seconds)}</span>
      <span>更新时间：${formatDate(model.updated_at)}</span>
    </div>
    <button class="secondary model-delete" data-id="${escapeHtml(model.id)}" type="button">删除</button>
  </div>`;
}

export const TrainingView = {
  render: () => `<section class="view-panel">
    <div class="view-head"><div><h2>RVC 训练</h2><p>单独管理训练素材、已训练模型和新一轮训练</p></div></div>
    <div class="train-flow">
      <div class="step-card">1. 选择音色<select id="trainingVoice">${qs('#voiceProfile').innerHTML}</select></div>
      <div class="step-card wide">2. 训练素材<div id="voiceSampleList" class="sample-list">选择音色后显示素材明细</div></div>
      <div class="step-card wide">3. 已训练模型<div id="voiceModelList" class="sample-list">选择音色后显示模型明细</div></div>
      <div class="step-card">4. 一键训练<select id="applioEpochs"><option value="10">10 轮</option><option value="40">40 轮</option><option value="80">80 轮</option></select><button id="trainApplioButton" type="button">准备并训练</button><span class="muted">会自动准备数据集</span></div>
      <div class="step-card wide">训练状态<div id="applioTrainMessage" class="message">模型已保存后可回工作台生成歌曲</div></div>
    </div>
  </section>`,
  mount: () => {
    const voice = qs('#trainingVoice');
    const message = qs('#applioTrainMessage');
    if (state.selectedVoiceId && voice.querySelector(`option[value="${CSS.escape(state.selectedVoiceId)}"]`)) {
      voice.value = state.selectedVoiceId;
    } else if (!voice.value) {
      const firstVoice = Array.from(voice.options).find((option) => option.value);
      if (firstVoice) {
        voice.value = firstVoice.value;
        state.selectedVoiceId = firstVoice.value;
      }
    }

    const loadSamples = async () => {
      const data = await api.voiceSamples(voice.value);
      qs('#voiceSampleList').innerHTML = (data.samples || []).map(sampleRow).join('') || '<div class="muted">暂无训练素材</div>';
    };
    const loadModels = async () => {
      const data = await api.voiceModels(voice.value, 'rvc_applio');
      qs('#voiceModelList').innerHTML = (data.models || []).map(modelRow).join('') || '<div class="muted">暂无已训练模型</div>';
    };
    const refresh = async () => {
      await loadSamples();
      await loadModels();
    };

    voice.addEventListener('change', refresh);
    refresh();

    qs('#voiceSampleList').addEventListener('click', async (event) => {
      const button = event.target.closest('.sample-delete');
      if (!button) return;
      if (!window.confirm('确定删除这个训练素材吗？')) return;
      const body = new FormData();
      body.append('voice_profile_id', voice.value);
      body.append('sample_id', button.dataset.id || '');
      message.textContent = '正在删除素材...';
      try {
        const data = await api.post('/api/delete-voice-sample', body);
        message.textContent = data.message || '素材已删除';
        await refresh();
      } catch (error) {
        message.textContent = error.message;
      }
    });

    qs('#voiceModelList').addEventListener('click', async (event) => {
      const button = event.target.closest('.model-delete');
      if (!button) return;
      if (!window.confirm('确定删除这个 RVC 模型吗？')) return;
      const body = new FormData();
      body.append('voice_model_id', button.dataset.id || '');
      message.textContent = '正在删除模型...';
      try {
        const data = await api.post('/api/delete-voice-model', body);
        message.textContent = data.message || '模型已删除';
        await refresh();
      } catch (error) {
        message.textContent = error.message;
      }
    });

    qs('#trainApplioButton').addEventListener('click', async () => {
      const body = new FormData();
      body.append('voice_profile_id', voice.value);
      body.append('epochs', qs('#applioEpochs').value);
      message.textContent = '正在准备数据集并训练...';
      try {
        const data = await api.post('/api/applio-train', body);
        message.textContent = `${data.message || '模型已保存'} · ${qs('#applioEpochs').value} 轮 · 用时 ${formatSeconds(data.training_seconds)}`;
        await refresh();
      } catch (error) {
        message.textContent = error.message;
      }
    });
  },
};
