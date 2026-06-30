import { escapeHtml } from '../utils.js';

function variantExplain(item) {
  const text = `${item.id || ''} ${item.name || ''} ${item.description || ''}`.toLowerCase();
  if (text.includes('clear') || text.includes('diction') || text.includes('清')) return '清晰版：优先让歌词更容易听懂，适合领导现场听字。';
  if (text.includes('timbre') || text.includes('strong') || text.includes('像')) return '音色版：优先贴近目标音色，可能比稳定版更有个性。';
  if (text.includes('stable') || text.includes('balance') || text.includes('自然')) return '稳定版：优先自然和少杂音，适合作为默认最终版。';
  return '对比版：用于快速比较听感，选中后可设为最终版本。';
}

export function VariantCard(item) {
  const explain = item.explain || variantExplain(item);
  return `<article class="variant-card"><h3>${escapeHtml(item.name || item.id || '对比版本')}</h3><audio controls src="${item.download_url || ''}"></audio><p>${escapeHtml(item.description || '用于对比听感')}</p><p class="variant-explain">${escapeHtml(explain)}</p><div class="button-row"><a class="download" href="${item.download_url || '#'}">下载 MP3</a><a class="download secondary" href="${item.download_wav_url || '#'}">下载 WAV</a><button class="secondary variant-select" data-id="${escapeHtml(item.id || '')}" type="button">设为最终版本</button><button class="secondary variant-feedback" data-id="${escapeHtml(item.id || '')}" type="button">标记喜欢</button></div></article>`;
}
