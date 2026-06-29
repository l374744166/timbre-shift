import { api } from './api.js';
import { state } from './state.js';
import { initRouter, navigate } from './router.js';
import { escapeHtml, formatNumber, qs } from './utils.js';
import { renderResult } from './views/DashboardView.js';

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
    const statusText = progress.status === 'completed' ? '已完成' : (progress.status === 'running' ? '运行中' : (progress.status === 'failed' ? '失败' : '待命'));
    qs('#progressStep') && (qs('#progressStep').textContent = progress.step || '待命');
    qs('#progressTime') && (qs('#progressTime').textContent = progress.status === 'completed' ? `完成用时 ${formatElapsed(progress.elapsed_seconds)}` : formatElapsed(progress.elapsed_seconds));
    qs('#progressBar') && (qs('#progressBar').style.width = `${Number(progress.percent || 0)}%`);
    qs('#progressStatus') && (qs('#progressStatus').textContent = statusText);
    qs('#progressStatus') && (qs('#progressStatus').className = `status-badge ${progress.status === 'completed' ? 'ok' : progress.status === 'failed' ? 'warn' : ''}`);
    renderProgressDetails(progress);
    if (progress.status === 'completed' && !state.lastResult && state.currentView === 'dashboard') {
      await restoreLatestResult();
    }
  } catch {}
}

function renderProgressDetails(progress) {
  const target = qs('#progressDetails');
  if (!target) return;
  const details = progress.details || {};
  if (details.task_type !== 'rvc_training') {
    target.innerHTML = '';
    target.classList.add('hidden');
    return;
  }
  const current = Number(details.current_epoch || 0);
  const total = Number(details.total_epochs || 0);
  const stage = details.stage || progress.step || '训练中';
  const saved = details.latest_saved_epoch ? `第 ${details.latest_saved_epoch} 轮已保存阶段模型` : '等待阶段保存';
  const percent = total > 0 ? Math.round((current / total) * 100) : Number(progress.percent || 0);
  target.classList.remove('hidden');
  target.innerHTML = `
    <div class="progress-detail-item"><span>训练轮数</span><strong>${current}/${total || '-'}</strong></div>
    <div class="progress-detail-item"><span>轮数进度</span><strong>${total ? `${percent}%` : '-'}</strong></div>
    <div class="progress-detail-item"><span>当前阶段</span><strong>${escapeHtml(stage)}</strong></div>
    <div class="progress-detail-item"><span>最新保存</span><strong>${escapeHtml(saved)}</strong></div>`;
}

function formatElapsed(value) {
  const seconds = Math.max(0, Number(value || 0));
  const minutes = Math.floor(seconds / 60);
  const rest = Math.floor(seconds % 60);
  return `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`;
}

async function refreshRecentHistory() {
  try {
    const data = await api.history();
    const jobs = (data.jobs || []).slice(0, 4);
    qs('#recentHistoryList').innerHTML = jobs.length ? jobs.map((job) => `
      <button class="mini-item recent-history-jump" type="button">
        <strong>${escapeHtml(job.song_title || '未命名歌曲')}</strong>
        <span>${escapeHtml(job.voice_profile_name || '未命名音色')} · ${engineLabel(job.engine_id)} · ${formatHistoryTime(job.created_at)}</span>
        <span>${formatNumber(job.total_seconds, 1)} 秒 · 打开生成历史</span>
      </button>`).join('') : '<div class="muted">暂无记录</div>';
  } catch {}
}

async function restoreLatestResult() {
  try {
    const data = await api.latestResult();
    if (state.currentView !== 'dashboard') return;
    renderResult(data);
    const message = qs('#message');
    if (message) message.textContent = data.message || '已恢复最近一次生成结果';
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
  await restoreLatestResult();
  setInterval(refreshProgress, 1200);
  setInterval(refreshRecentHistory, 15000);
  qs('#recentHistoryList')?.addEventListener('click', (event) => {
    if (!event.target.closest('.recent-history-jump')) return;
    navigate('history');
  });
  qs('#cancelTaskButton')?.addEventListener('click', async () => {
    await api.cancelTask();
    await refreshProgress();
  });
  qs('#demoPresetButton')?.addEventListener('click', () => navigate('dashboard', { demo: true }));
  qs('#quickTrainButton')?.addEventListener('click', () => navigate('training'));
}

boot();
