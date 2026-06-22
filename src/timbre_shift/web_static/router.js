import { state } from './state.js';
import { qsa, qs } from './utils.js';
import { DashboardView } from './views/DashboardView.js';
import { VoiceLibraryView } from './views/VoiceLibraryView.js';
import { SongLibraryView } from './views/SongLibraryView.js';
import { TrainingView } from './views/TrainingView.js';
import { HistoryView } from './views/HistoryView.js';
import { EnvironmentView } from './views/EnvironmentView.js';

const views = {
  dashboard: DashboardView,
  voices: VoiceLibraryView,
  songs: SongLibraryView,
  training: TrainingView,
  history: HistoryView,
  environment: EnvironmentView,
  settings: { render: () => '<section class="view-panel"><h2>设置</h2><p class="muted">高级参数和调试信息会逐步收进这里。</p></section>', mount: () => {} },
};

export function navigate(view, options = {}) {
  state.currentView = view;
  qsa('.nav-item').forEach((item) => item.classList.toggle('active', item.dataset.view === view));
  const target = views[view] || views.dashboard;
  qs('#viewRoot').innerHTML = target.render(options);
  target.mount?.(options);
}

export function initRouter() {
  qsa('.nav-item').forEach((button) => button.addEventListener('click', () => navigate(button.dataset.view)));
  navigate('dashboard');
}
