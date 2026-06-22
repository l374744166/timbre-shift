import { escapeHtml, formatNumber } from '../utils.js';
export function HistoryItem(job) {
  return `<article class="history-row"><strong>${escapeHtml(job.song_title || '未命名歌曲')}</strong><span>${escapeHtml(job.voice_profile_name || '未命名音色')}</span><span>${escapeHtml(job.engine_id || '-')}</span><span>${formatNumber(job.total_seconds, 1)}秒</span><div class="button-row"><a class="download secondary" href="/download/history/${encodeURIComponent(job.id)}/final.mp3">播放/下载</a></div></article>`;
}
