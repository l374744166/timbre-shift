import { state } from '../state.js';
import { escapeHtml } from '../utils.js';

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


function rvcTrainingPanel() {
  if (state.selectedEngine !== 'rvc_applio') return '';
  return `<section class="step-section rvc-inline-panel" id="rvcInlinePanel">
    <div class="section-head-row"><div><h3>RVC 训练和模型</h3><p class="muted">创建音色库、添加训练素材、训练模型分开显示；训练前会弹窗确认轮数。</p></div></div>
    <div class="train-flow">
      <div class="step-card wide"><strong>训练素材</strong><div id="dashboardSampleList" class="sample-list">先选择一个 RVC 音色库</div></div>
      <div class="step-card wide"><strong>已训练模型</strong><div id="dashboardModelList" class="sample-list">先选择一个 RVC 音色库</div></div>
      <div class="step-card"><strong>训练模型</strong><button id="dashboardTrainApplioButton" type="button">打开训练设置</button><span class="muted">选择轮数后再开始</span></div>
      <div class="step-card wide"><strong>训练状态</strong><div id="dashboardTrainMessage" class="message">选择音色后可训练模型；生成时会自动使用可用模型，也可以手动选择模型。</div></div>
    </div>
    <div class="modal hidden" id="rvcTrainModal" role="dialog" aria-modal="true" aria-labelledby="rvcTrainModalTitle">
      <div class="modal-panel">
        <div class="modal-head"><div><h3 id="rvcTrainModalTitle">RVC 训练设置</h3><p class="muted" id="rvcTrainModalSubtitle">确认训练轮数后再开始</p></div><button class="secondary modal-close" id="rvcTrainModalClose" type="button">×</button></div>
        <div class="settings-grid">
          <label>训练轮数<select id="dashboardApplioEpochs"><option value="10">10 轮 · 快速测试</option><option value="40">40 轮 · 日常推荐</option><option value="80">80 轮 · 更认真训练</option><option value="120">120 轮 · 高质量训练</option></select></label>
          <label>当前音色<input id="rvcTrainVoiceName" type="text" readonly value="未选择"></label>
          <label>训练素材<input id="rvcTrainSampleCount" type="text" readonly value="0 个"></label>
        </div>
        <p class="muted" id="rvcTrainModalHint">开始后会自动准备数据集，然后进入训练。你可以离开页面，训练会继续跑。</p>
        <div class="button-row"><button id="rvcTrainModalStart" type="button">开始训练</button><button class="secondary" id="rvcTrainModalCancel" type="button">取消</button></div>
      </div>
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

export { formatSeconds, rvcTrainingPanel, sampleRow, modelRow };
