import { escapeHtml } from '../utils.js';
export function VariantCard(item) {
  return `<article class="variant-card"><h3>${escapeHtml(item.name || item.id || '对比版本')}</h3><audio controls src="${item.download_url || ''}"></audio><p>${escapeHtml(item.description || '用于对比听感')}</p><div class="button-row"><a class="download" href="${item.download_url || '#'}">下载 MP3</a><a class="download secondary" href="${item.download_wav_url || '#'}">下载 WAV</a><button class="secondary variant-select" data-id="${escapeHtml(item.id || '')}" type="button">设为最终版本</button><button class="secondary variant-feedback" data-id="${escapeHtml(item.id || '')}" type="button">标记喜欢</button></div></article>`;
}
