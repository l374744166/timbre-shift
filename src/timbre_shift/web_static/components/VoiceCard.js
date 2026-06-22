import { escapeHtml } from '../utils.js';
export function VoiceCard(option, selectedId = '', mode = 'seedvc') {
  const count = Number(option.dataset.sampleCount || 0);
  const modelCount = Number(option.dataset.rvcModelCount || 0);
  const isRvc = mode === 'rvc_applio';
  const name = escapeHtml(option.textContent.trim() || '未命名音色');
  if (isRvc) {
    const status = modelCount > 0 ? `已训练 ${modelCount} 个 RVC 模型` : (count > 0 ? '尚未训练 RVC 模型' : '空音色库，等待训练素材');
    const trainLabel = modelCount > 0 ? '继续训练' : '训练模型';
    const materialText = count > 0 ? `训练素材：${count} 条人声` : '训练素材：暂无';
    const quality = count >= 3 ? '素材较适合演示' : '建议补充多首干声素材';
    return `<article class="resource-card ${option.value === selectedId ? 'selected' : ''}" data-voice-id="${escapeHtml(option.value)}">
      <div><h3>${name}</h3><p>${status}</p></div>
      <div class="card-actions"><button type="button" class="voice-train" data-id="${escapeHtml(option.value)}">${trainLabel}</button><button type="button" class="secondary voice-select" data-id="${escapeHtml(option.value)}">选择生成</button><button type="button" class="secondary danger voice-delete" data-id="${escapeHtml(option.value)}" data-name="${name}">删除</button></div>
      <div class="card-meta"><span>RVC 模型：${modelCount} 个</span><span>${materialText}</span><span>${quality}</span></div>
    </article>`;
  }
  const status = count > 0 ? '可作为快速参考声音' : '需要上传参考声音';
  const quality = count >= 3 ? '较适合演示' : '建议准备 15-30 秒清晰声音';
  return `<article class="resource-card ${option.value === selectedId ? 'selected' : ''}" data-voice-id="${escapeHtml(option.value)}">
    <div><h3>${name}</h3><p>${status}</p></div>
    <div class="card-meta"><span>${count} 个参考素材</span><span>质量提示：${quality}</span><span>Seed-VC：不需要训练</span></div>
    <div class="card-actions"><button type="button" class="secondary voice-select" data-id="${escapeHtml(option.value)}">选择参考声音</button><button type="button" class="secondary danger voice-delete" data-id="${escapeHtml(option.value)}" data-name="${name}">删除</button></div>
  </article>`;
}
