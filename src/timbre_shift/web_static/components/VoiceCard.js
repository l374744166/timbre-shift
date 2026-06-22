import { escapeHtml } from '../utils.js';
export function VoiceCard(option, selectedId = '') {
  const count = Number(option.dataset.sampleCount || 0);
  const trained = count > 0 ? '可用于参考 / 训练' : '需要添加素材';
  return `<article class="resource-card ${option.value === selectedId ? 'selected' : ''}" data-voice-id="${escapeHtml(option.value)}">
    <div><h3>${escapeHtml(option.textContent.trim() || '未命名音色')}</h3><p>${trained}</p></div>
    <div class="card-meta"><span>${count} 个素材</span><span>质量提示：${count >= 3 ? '较适合演示' : '建议补充素材'}</span></div>
    <div class="card-actions"><button type="button" class="secondary voice-select" data-id="${escapeHtml(option.value)}">选择</button><button type="button" class="secondary voice-train" data-id="${escapeHtml(option.value)}">训练模型</button></div>
  </article>`;
}
