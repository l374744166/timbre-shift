import { escapeHtml } from '../utils.js';
export function VoiceCard(option, selectedId = '', mode = 'seedvc') {
  const count = Number(option.dataset.sampleCount || 0);
  const modelCount = Number(option.dataset.rvcModelCount || 0);
  const isRvc = mode === 'rvc_applio';
  const status = isRvc
    ? (modelCount > 0 ? `已训练 ${modelCount} 个 RVC 模型` : (count > 0 ? '有素材，尚未训练模型' : '需要添加训练素材'))
    : (count > 0 ? '可作为快速参考声音' : '需要上传参考声音');
  const quality = count >= 3 ? '较适合演示' : isRvc ? '建议补充多首干声素材' : '建议准备 15-30 秒清晰声音';
  const modelStatus = modelCount > 0 ? `RVC 模型：${modelCount} 个已训练` : 'RVC 模型：未训练';
  return `<article class="resource-card ${option.value === selectedId ? 'selected' : ''}" data-voice-id="${escapeHtml(option.value)}">
    <div><h3>${escapeHtml(option.textContent.trim() || '未命名音色')}</h3><p>${status}</p></div>
    <div class="card-meta"><span>${count} 个素材</span><span>质量提示：${quality}</span><span>${isRvc ? modelStatus : 'Seed-VC：不需要训练'}</span></div>
    <div class="card-actions"><button type="button" class="secondary voice-select" data-id="${escapeHtml(option.value)}">${isRvc ? '选择音色库' : '选择参考声音'}</button>${isRvc ? `<button type="button" class="secondary voice-train" data-id="${escapeHtml(option.value)}">训练模型</button>` : ''}</div>
  </article>`;
}
