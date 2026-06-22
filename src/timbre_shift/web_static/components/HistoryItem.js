import { escapeHtml, formatNumber } from '../utils.js';
export function HistoryItem(job) {
  const id = encodeURIComponent(job.id || '');
  const actions = [
    job.has_mp3 ? `<a class="download secondary" href="/download/history/${id}/final.mp3">成品 MP3</a>` : '',
    job.has_wav ? `<a class="download secondary" href="/download/history/${id}/final.wav">成品 WAV</a>` : '',
    job.has_dry_vocal_mp3 ? `<a class="download secondary" href="/download/history/${id}/dry_vocal.mp3">干声 MP3</a>` : '',
    job.has_dry_vocal_wav ? `<a class="download secondary" href="/download/history/${id}/dry_vocal.wav">干声 WAV</a>` : '',
  ].filter(Boolean).join('');
  const fallback = actions || '<span class="muted">文件缺失</span>';
  return `<article class="history-row"><strong>${escapeHtml(job.song_title || '未命名歌曲')}</strong><span>${escapeHtml(job.voice_profile_name || '未命名音色')}</span><span>${escapeHtml(job.engine_id || '-')}</span><span>${formatNumber(job.total_seconds, 1)}秒</span><div class="button-row">${fallback}</div></article>`;
}
