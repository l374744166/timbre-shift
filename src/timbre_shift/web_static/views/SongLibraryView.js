import { qs } from '../utils.js';
import { SongCard } from '../components/SongCard.js';
export const SongLibraryView = { render: () => { const options = Array.from(qs('#songLibrary').options).filter((option) => option.value); return `<section class="view-panel"><div class="view-head"><div><h2>歌曲库</h2><p>查看已保存歌曲和分离状态</p></div><button>上传新歌曲</button></div><div class="resource-grid">${options.map((option) => SongCard(option)).join('') || '<div class="empty-state">暂无歌曲，工作台可直接上传。</div>'}</div></section>`; }, mount: () => {} };
