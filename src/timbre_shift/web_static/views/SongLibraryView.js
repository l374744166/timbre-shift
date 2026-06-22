import { qs } from '../utils.js';
import { state } from '../state.js';
import { navigate } from '../router.js';
import { SongCard } from '../components/SongCard.js';

export const SongLibraryView = {
  render: () => {
    const options = Array.from(qs('#songLibrary').options).filter((option) => option.value);
    return `<section class="view-panel"><div class="view-head"><div><h2>歌曲库</h2><p>查看已保存歌曲和分离状态</p></div><button id="uploadSongFromLibrary" type="button">上传新歌曲</button></div><div class="resource-grid" id="librarySongCards">${options.map((option) => SongCard(option, state.selectedSongId)).join('') || '<div class="empty-state">暂无歌曲，工作台可直接上传。</div>'}</div></section>`;
  },
  mount: () => {
    qs('#uploadSongFromLibrary')?.addEventListener('click', () => navigate('dashboard'));
    qs('#librarySongCards')?.addEventListener('click', (event) => {
      const button = event.target.closest('.song-select');
      if (!button) return;
      state.selectedSongId = button.dataset.id;
      qs('#songLibrary').value = state.selectedSongId;
      navigate('dashboard');
    });
  },
};
