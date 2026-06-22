import { api } from '../api.js';
import { qs } from '../utils.js';
import { HistoryItem } from '../components/HistoryItem.js';
export const HistoryView = { render: () => `<section class="view-panel"><div class="view-head"><div><h2>生成历史</h2><p>播放、下载、复用以前的结果</p></div></div><div id="historyList" class="history-list">加载中...</div></section>`, mount: async () => { const data = await api.history(); qs('#historyList').innerHTML = (data.jobs || []).map(HistoryItem).join('') || '<div class="empty-state">暂无生成历史</div>'; } };
