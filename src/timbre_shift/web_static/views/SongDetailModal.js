import { api } from '../api.js';
import { escapeHtml, formatNumber, qs } from '../utils.js';

function songOption(songId) {
  return qs('#songLibrary')?.querySelector(`option[value="${CSS.escape(songId || '')}"]`) || null;
}

function sourceKindLabel(kind) {
  return kind === 'clean_vocal' ? '干净人声，可跳过 Demucs' : '完整歌曲，生成时需要做人声分离';
}

function recommendation(kind) {
  if (kind === 'clean_vocal') return '适合 Seed-VC 快速试听，也适合 RVC 正式生成；速度更快，变量更少。';
  return '适合完整歌曲生成；如果是 AI 歌或伴奏很黏，建议使用高质量分离和源人声修复。';
}

function recentRows(jobs) {
  return jobs.slice(0, 4).map((job) => `<div class="detail-row"><strong>${escapeHtml(job.voice_profile_name || '未命名音色')}</strong><span>${escapeHtml(job.engine_id || '-')} · ${formatNumber(job.total_seconds, 1)} 秒 · ${escapeHtml(job.created_at || '时间未知')}</span></div>`).join('') || '<div class="muted">暂无生成记录</div>';
}

export function songDetailModal() {
  return `<div class="modal hidden" id="songDetailModal"><div class="modal-panel song-detail-modal"><div class="modal-head"><div><h3 id="songDetailTitle">歌曲详情</h3><p class="muted" id="songDetailSubtitle">查看分离状态和使用建议</p></div><button class="secondary modal-close" id="songDetailClose" type="button">×</button></div><div id="songDetailBody" class="song-detail-body"><div class="muted">请选择歌曲</div></div><div class="button-row"><button id="songDetailSelect" type="button">选择用于生成</button></div></div></div>`;
}

export async function openSongDetail(songId, { selectSong } = {}) {
  const option = songOption(songId);
  if (!option) return;
  const title = option.textContent.trim() || '未命名歌曲';
  const sourceKind = option.dataset.sourceKind || 'full_song';
  qs('#songDetailTitle').textContent = title;
  qs('#songDetailSubtitle').textContent = sourceKindLabel(sourceKind);
  qs('#songDetailBody').innerHTML = '<div class="muted">正在读取最近生成记录...</div>';
  qs('#songDetailModal')?.classList.remove('hidden');

  let jobs = [];
  try {
    const data = await api.history();
    jobs = (data.jobs || []).filter((job) => (job.song_title || '') === title);
  } catch {
    jobs = [];
  }

  qs('#songDetailBody').innerHTML = `<div class="detail-grid"><div class="detail-stat"><span>歌曲类型</span><strong>${escapeHtml(sourceKindLabel(sourceKind))}</strong></div><div class="detail-stat"><span>分离状态</span><strong>${sourceKind === 'clean_vocal' ? '可跳过分离' : '生成时自动分离'}</strong></div><div class="detail-stat"><span>最近生成</span><strong>${jobs.length} 次</strong></div></div><div class="detail-columns"><section><h4>使用建议</h4><div class="detail-row"><strong>${sourceKind === 'clean_vocal' ? '干声优先' : '完整歌曲流程'}</strong><span>${escapeHtml(recommendation(sourceKind))}</span></div></section><section><h4>最近生成</h4>${recentRows(jobs)}</section></div><p class="muted">如果源歌人声本身很脏，RVC 会放大毛刺；演示时优先选择干净歌曲或高质量分离。</p>`;
  qs('#songDetailSelect').onclick = () => {
    selectSong?.(songId);
    closeSongDetail();
  };
}

export function closeSongDetail() {
  qs('#songDetailModal')?.classList.add('hidden');
}
