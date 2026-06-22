import { api } from './api.js';
import { state } from './state.js';
import { initRouter, navigate } from './router.js';
import { qs } from './utils.js';

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
      <div class="mini-item">
        <strong>${job.song_title || '未命名歌曲'}</strong>
        <span>${job.voice_profile_name || '未命名音色'} · ${job.engine_id || '-'}</span>
      </div>`).join('') : '<div class="muted">暂无记录</div>';
  } catch {}
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
  qs('#demoPresetButton').addEventListener('click', () => navigate('dashboard', { demo: true }));
  qs('#quickTrainButton').addEventListener('click', () => navigate('training'));
}

boot();
