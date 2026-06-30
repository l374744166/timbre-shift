import { api } from '../api.js';
import { escapeHtml, formatNumber, qs } from '../utils.js';

function qualityHint(sampleCount, modelCount, isRvc) {
  if (!isRvc) return sampleCount > 0 ? '可用于 Seed-VC 快速试听' : '需要补充参考声音';
  if (modelCount > 0 && sampleCount >= 3) return '适合演示，已有训练模型和多条素材';
  if (modelCount > 0) return '已有模型，可继续补充素材后再训练新版';
  if (sampleCount > 0) return '已有素材，但还需要训练 RVC 模型';
  return '空音色库，请先添加训练素材';
}

function sampleList(samples) {
  return samples.map((sample) => `<div class="detail-row"><strong>${escapeHtml(sample.name || sample.id || '素材')}</strong><span>${formatNumber(sample.duration_seconds, 1)} 秒 · ${escapeHtml(sample.source_type || '声音素材')}</span></div>`).join('') || '<div class="muted">暂无素材</div>';
}

function modelList(models) {
  return models.map((model) => `<div class="detail-row"><strong>${escapeHtml(model.name || model.model_name || 'RVC 模型')}</strong><span>${escapeHtml(model.status || '-')} · ${model.epochs ? `${escapeHtml(model.epochs)} 轮 · ` : ''}${formatNumber(model.dataset_seconds, 1)} 秒素材</span></div>`).join('') || '<div class="muted">暂无模型</div>';
}

export function voiceDetailModal() {
  return `<div class="modal hidden" id="voiceDetailModal"><div class="modal-panel voice-detail-modal"><div class="modal-head"><div><h3 id="voiceDetailTitle">音色详情</h3><p class="muted" id="voiceDetailSubtitle">查看素材、模型和演示建议</p></div><button class="secondary modal-close" id="voiceDetailClose" type="button">×</button></div><div id="voiceDetailBody" class="voice-detail-body"><div class="muted">请选择音色</div></div><div class="button-row"><button class="secondary" id="voiceDetailSelect" type="button">选择用于生成</button><button id="voiceDetailTrain" type="button">去训练设置</button></div></div></div>`;
}

export async function openVoiceDetail({ voiceId, mode, selectVoice, loadRvcTrainingDetails }) {
  const option = qs('#voiceProfile')?.querySelector(`option[value="${CSS.escape(voiceId || '')}"]`);
  if (!option) return;
  const isRvc = mode === 'rvc_applio';
  const sampleCount = Number(option.dataset.sampleCount || 0);
  const modelCount = Number(option.dataset.rvcModelCount || 0);
  const name = option.textContent.trim() || '未命名音色';
  qs('#voiceDetailTitle').textContent = name;
  qs('#voiceDetailSubtitle').textContent = qualityHint(sampleCount, modelCount, isRvc);
  qs('#voiceDetailBody').innerHTML = '<div class="muted">正在读取详情...</div>';
  qs('#voiceDetailModal')?.classList.remove('hidden');

  let samples = [];
  let models = [];
  try {
    const sampleData = await api.voiceSamples(voiceId);
    samples = sampleData.samples || [];
    if (isRvc) {
      const modelData = await api.voiceModels(voiceId, 'rvc_applio');
      models = modelData.models || [];
    }
  } catch (error) {
    qs('#voiceDetailBody').innerHTML = `<div class="message error">${escapeHtml(error.message)}</div>`;
    return;
  }

  qs('#voiceDetailBody').innerHTML = `<div class="detail-grid"><div class="detail-stat"><span>素材数量</span><strong>${samples.length || sampleCount}</strong></div><div class="detail-stat"><span>RVC 模型</span><strong>${isRvc ? (models.length || modelCount) : '不需要'}</strong></div><div class="detail-stat"><span>推荐程度</span><strong>${escapeHtml(qualityHint(samples.length || sampleCount, models.length || modelCount, isRvc))}</strong></div></div><div class="detail-columns"><section><h4>素材列表</h4>${sampleList(samples)}</section><section><h4>模型列表</h4>${isRvc ? modelList(models) : '<div class="muted">Seed-VC 不需要训练模型</div>'}</section></div><p class="muted">删除素材或模型仍在工作台训练区操作，避免误删。</p>`;

  qs('#voiceDetailSelect').onclick = async () => {
    selectVoice?.(voiceId);
    await loadRvcTrainingDetails?.();
    closeVoiceDetail();
  };
  qs('#voiceDetailTrain').onclick = async () => {
    selectVoice?.(voiceId);
    await loadRvcTrainingDetails?.();
    closeVoiceDetail();
    qs('#rvcInlinePanel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
}

export function closeVoiceDetail() {
  qs('#voiceDetailModal')?.classList.add('hidden');
}
