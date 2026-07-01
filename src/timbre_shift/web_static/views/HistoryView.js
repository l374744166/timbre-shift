import { api } from '../api.js';
import { qs } from '../utils.js';
import { HistoryItem } from '../components/HistoryItem.js';
import { closeHistoryDetail, historyDetailModal, openHistoryDetail } from './HistoryDetailModal.js';

export const HistoryView = {
  render: () => `<section class="view-panel"><div class="view-head"><div><h2>生成历史</h2><p>播放、下载、复用以前的结果</p></div></div><div id="historyMessage" class="message"></div><div id="historyList" class="history-list">加载中...</div></section>${historyDetailModal()}`,
  mount: async () => {
    let jobs = [];
    const render = () => {
      qs('#historyList').innerHTML = jobs.map(HistoryItem).join('') || '<div class="empty-state">暂无生成历史</div>';
    };
    const data = await api.history();
    jobs = data.jobs || [];
    render();
    qs('#historyList')?.addEventListener('click', (event) => {
      const detailButton = event.target.closest('.history-detail');
      if (!detailButton) return;
      const job = jobs.find((item) => item.id === decodeURIComponent(detailButton.dataset.id || ''));
      if (!job) return;
      openHistoryDetail(job, {
        onDeleted: (jobId, message) => {
          jobs = jobs.filter((item) => item.id !== jobId);
          render();
          qs('#historyMessage').textContent = message;
        },
      });
    });
    qs('#historyDetailClose')?.addEventListener('click', closeHistoryDetail);
    qs('#historyDetailModal')?.addEventListener('click', (event) => { if (event.target.id === 'historyDetailModal') closeHistoryDetail(); });
  },
};
