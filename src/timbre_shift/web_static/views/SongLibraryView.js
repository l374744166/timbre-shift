import { qs } from '../utils.js';
import { api } from '../api.js';
import { state } from '../state.js';
import { navigate } from '../router.js';
import { SongCard } from '../components/SongCard.js';
import { closeSongDetail, openSongDetail, songDetailModal } from './SongDetailModal.js';

export const SongLibraryView = {
  render: () => {
    const options = Array.from(qs('#songLibrary').options).filter((option) => option.value);
    return `<section class="view-panel"><div class="view-head"><div><h2>歌曲库</h2><p>查看已保存歌曲和分离状态</p></div><button id="uploadSongFromLibrary" type="button">上传新歌曲</button></div><div class="resource-grid" id="librarySongCards">${options.map((option) => SongCard(option, state.selectedSongId)).join('') || '<div class="empty-state">暂无歌曲，工作台可直接上传。</div>'}</div></section>${songDetailModal()}`;
  },
  mount: () => {
    const selectSong = (id) => {
      state.selectedSongId = id;
      qs('#songLibrary').value = state.selectedSongId;
      navigate('dashboard');
    };
    qs('#uploadSongFromLibrary')?.addEventListener('click', () => navigate('dashboard'));
    qs('#songDetailClose')?.addEventListener('click', closeSongDetail);
    qs('#songDetailModal')?.addEventListener('click', (event) => { if (event.target.id === 'songDetailModal') closeSongDetail(); });
    qs('#librarySongCards')?.addEventListener('click', async (event) => {
      const deleteButton = event.target.closest('.song-delete');
      if (deleteButton) {
        const name = deleteButton.dataset.name || '这首歌';
        if (!window.confirm(`删除歌曲「${name}」？`)) return;
        const body = new FormData();
        body.append('song_id', deleteButton.dataset.id || '');
        await api.post('/api/delete-song', body);
        qs('#songLibrary')?.querySelector(`option[value="${CSS.escape(deleteButton.dataset.id || '')}"]`)?.remove();
        if (state.selectedSongId === deleteButton.dataset.id) state.selectedSongId = '';
        navigate('songs');
        return;
      }
      const detailButton = event.target.closest('.song-detail');
      if (detailButton) {
        await openSongDetail(detailButton.dataset.id, { selectSong });
        return;
      }
      const button = event.target.closest('.song-select');
      if (!button) return;
      selectSong(button.dataset.id);
    });
  },
};
