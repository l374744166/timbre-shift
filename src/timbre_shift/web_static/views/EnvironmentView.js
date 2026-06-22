import { api } from '../api.js';
import { qs } from '../utils.js';
export const EnvironmentView = { render: () => `<section class="view-panel"><div class="view-head"><div><h2>环境检查</h2><p>技术细节集中放在这里，不打扰主流程</p></div><button id="rerunEnv">重新检测</button></div><pre id="envReport" class="metrics">检查中...</pre></section>`, mount: async () => { const run = async () => { const data = await api.check(); qs('#envReport').textContent = data.text || JSON.stringify(data, null, 2); }; qs('#rerunEnv').addEventListener('click', run); await run(); } };
