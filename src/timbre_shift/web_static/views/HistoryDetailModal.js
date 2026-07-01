import { api } from '../api.js';
import { navigate } from '../router.js';
import { escapeHtml, formatNumber, qs } from '../utils.js';
import { renderResult } from './DashboardView.js';

const presetLabels = {
  stable_balanced: '自然稳定',
  clear_diction: '歌词更清楚',
  stronger_timbre_safe: '更像目标音色',
};
const styleLabels = {
  neutral: '不额外修饰',
  close_intimate: '贴脸清晰',
  narrative_soft: '柔和抒情',
  low_thick: '温暖厚实',
  bright_pop: '明亮流行',
};
const mixLabels = { natural: '自然', vocal_forward: '人声靠前', blend_with_backing: '融进伴奏' };

function label(value, map) {
  return map[value] || value || '-';
}

function audioBlock(title, url) {
  return url ? `<div class="history-player"><h4>${escapeHtml(title)}</h4><audio controls src="${url}"></audio></div>` : '';
}

function fileLinks(job, id) {
  return [
    job.has_mp3 ? `<a class="download" href="/download/history/${id}/final.mp3">成品 MP3</a>` : '',
    job.has_wav ? `<a class="download secondary" href="/download/history/${id}/final.wav">成品 WAV</a>` : '',
    job.has_dry_vocal_mp3 ? `<a class="download secondary" href="/download/history/${id}/dry_vocal.mp3">干声 MP3</a>` : '',
    job.has_dry_vocal_wav ? `<a class="download secondary" href="/download/history/${id}/dry_vocal.wav">干声 WAV</a>` : '',
  ].filter(Boolean).join('');
}

export function historyDetailModal() {
  return `<div class="modal hidden" id="historyDetailModal"><div class="modal-panel history-detail-modal"><div class="modal-head"><div><h3 id="historyDetailTitle">生成详情</h3><p class="muted" id="historyDetailSubtitle">查看播放、下载和本次参数</p></div><button class="secondary modal-close" id="historyDetailClose" type="button">×</button></div><div id="historyDetailBody" class="history-detail-body"></div><div id="historyDetailMessage" class="message"></div><div class="button-row"><button id="historyRestoreButton" type="button">设为当前结果</button><button class="secondary danger" id="historyDeleteButton" type="button">删除这条历史</button></div></div></div>`;
}

export function openHistoryDetail(job, { onDeleted } = {}) {
  const id = encodeURIComponent(job.id || '');
  qs('#historyDetailTitle').textContent = job.song_title || '未命名歌曲';
  qs('#historyDetailSubtitle').textContent = `${job.voice_profile_name || '未命名音色'} · ${job.engine_id || '-'} · ${formatNumber(job.total_seconds, 1)} 秒`;
  qs('#historyDetailBody').innerHTML = `<div class="result-grid single-result-grid">${audioBlock('成品歌曲', job.has_mp3 ? `/download/history/${id}/final.mp3` : (job.has_wav ? `/download/history/${id}/final.wav` : ''))}${audioBlock('干声人声', job.has_dry_vocal_mp3 ? `/download/history/${id}/dry_vocal.mp3` : (job.has_dry_vocal_wav ? `/download/history/${id}/dry_vocal.wav` : ''))}</div><div class="result-facts"><div class="result-fact"><span>目标音色</span><strong>${escapeHtml(job.voice_profile_name || '-')}</strong></div><div class="result-fact"><span>引擎</span><strong>${escapeHtml(job.engine_id || '-')}</strong></div><div class="result-fact"><span>生成目标</span><strong>${escapeHtml(label(job.rvc_preset, presetLabels))}</strong></div><div class="result-fact"><span>人声修饰</span><strong>${escapeHtml(label(job.vocal_style, styleLabels))}</strong></div><div class="result-fact"><span>混音风格</span><strong>${escapeHtml(label(job.mix_style, mixLabels))}</strong></div><div class="result-fact"><span>问题提示</span><strong>${escapeHtml(job.diagnostic_summary || '暂无明显问题')}</strong></div></div><div class="button-row">${fileLinks(job, id) || '<span class="muted">文件缺失</span>'}</div>`;
  qs('#historyDetailMessage').textContent = '';
  qs('#historyDetailModal')?.classList.remove('hidden');

  qs('#historyRestoreButton').onclick = async () => {
    const body = new FormData();
    body.append('job_id', job.id || '');
    qs('#historyDetailMessage').textContent = '正在设为当前结果...';
    try {
      await api.post('/api/history-restore', body);
      const result = await api.latestResult();
      closeHistoryDetail();
      navigate('dashboard');
      renderResult(result, { scroll: true });
    } catch (error) {
      qs('#historyDetailMessage').textContent = error.message;
    }
  };
  qs('#historyDeleteButton').onclick = async () => {
    if (!window.confirm('确定删除这条生成历史吗？')) return;
    const body = new FormData();
    body.append('job_id', job.id || '');
    qs('#historyDetailMessage').textContent = '正在删除历史...';
    try {
      const data = await api.post('/api/history-delete', body);
      closeHistoryDetail();
      onDeleted?.(job.id, data.message || '历史记录已删除');
    } catch (error) {
      qs('#historyDetailMessage').textContent = error.message;
    }
  };
}

export function closeHistoryDetail() {
  qs('#historyDetailModal')?.classList.add('hidden');
}
