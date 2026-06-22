import { escapeHtml } from '../utils.js';
export function SongCard(option, selectedId = '') {
  const separated = option.dataset.sourceKind === 'clean_vocal' ? '可跳过 Demucs' : '需要分离';
  return `<article class="resource-card ${option.value === selectedId ? 'selected' : ''}" data-song-id="${escapeHtml(option.value)}">
    <div><h3>${escapeHtml(option.textContent.trim() || '未命名歌曲')}</h3><p>${separated}</p></div>
    <div class="card-meta"><span>歌曲库</span><span>最近生成次数：-</span></div>
    <div class="card-actions"><button type="button" class="secondary song-select" data-id="${escapeHtml(option.value)}">选择</button></div>
  </article>`;
}
