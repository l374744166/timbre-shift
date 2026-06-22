import { api } from './api.js';
import { state } from './state.js';
import { initRouter, navigate } from './router.js';
import { escapeHtml, formatNumber, qs } from './utils.js';

const form = document.getElementById('form');

async function refreshEnvironment() {
  const report = await api.check();
  const ready = Boolean(report.ready);
  qs('#envStatus').textContent = ready ? '环境就绪' : '需要处理';
  qs('#envStatus').className = `status-pill ${ready ? 'ok' : 'warn'}`;
  const text = report.text || '';
  qs('#seedvcStatus').textContent = text.includes('Seed-VC') || text.includes('inference.py') ? 'Seed-VC 可用' : 'Seed-VC 检查';
  qs('#seedvcStatus').className = 'status-pill ok';
  qs('#applioStatus').textContent = 'Applio RVC 可用';
  qs('#applioStatus').className = 'status-pill ok';
}

async function refreshProgress() {
  try {
    const progress = await api.progress();
    state.progress = progress;
    qs('#progressStep').textContent = progress.step || '待命';
    qs('#progressTime').textContent = progress.elapsed_label || '00:00';
    qs('#progressBar').style.width = `${Number(progress.percent || 0)}%`;
  } catch {}
}

async function refreshRecentHistory() {
  try {
    const data = await api.history();
    const jobs = (data.jobs || []).slice(0, 4);
    qs('#recentHistoryList').innerHTML = jobs.length ? jobs.map((job) => `
      <a class="mini-item" href="/download/history/${encodeURIComponent(job.id)}/final.mp3">
        <strong>${escapeHtml(job.song_title || '未命名歌曲')}</strong>
        <span>${escapeHtml(job.voice_profile_name || '未命名音色')} · ${engineLabel(job.engine_id)} · ${formatHistoryTime(job.created_at)}</span>
        <span>${formatNumber(job.total_seconds, 1)} 秒 · 点击播放/下载</span>
      </a>`).join('') : '<div class="muted">暂无记录</div>';
  } catch {}
}

function engineLabel(engineId) {
  if (engineId === 'rvc_applio') return 'RVC';
  if (engineId === 'seedvc') return 'Seed-VC';
  return escapeHtml(engineId || '-');
}

function formatHistoryTime(value) {
  if (!value) return '时间未知';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '时间未知';
  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

async function boot() {
  initRouter();
  await refreshEnvironment();
  await refreshRecentHistory();
  await refreshProgress();
  setInterval(refreshProgress, 1200);
  setInterval(refreshRecentHistory, 15000);
  qs('#cancelTaskButton').addEventListener('click', async () => {
    await api.cancelTask();
    await refreshProgress();
  });
  qs('#demoPresetButton')?.addEventListener('click', () => navigate('dashboard', { demo: true }));
  qs('#quickTrainButton')?.addEventListener('click', () => navigate('training'));
}

boot();
