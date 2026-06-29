import { qs } from '../utils.js';
import { api } from '../api.js';
import { state, setSelectedEngine } from '../state.js';
import { navigate } from '../router.js';
import { VoiceCard } from '../components/VoiceCard.js';

export const VoiceLibraryView = {
  render: () => {
    const options = Array.from(qs('#voiceProfile').options).filter((option) => option.value);
    return `<section class="view-panel"><div class="view-head"><div><h2>音色库</h2><p>资源卡片管理目标音色、素材和训练状态</p></div><button id="newVoiceFromLibrary" type="button">新建音色</button></div><div class="toolbar"><input placeholder="搜索音色"><select><option>全部</option><option>已训练</option><option>未训练</option><option>素材不足</option></select></div><div class="resource-grid" id="libraryVoiceCards">${options.map((option) => VoiceCard(option, state.selectedVoiceId, 'rvc_applio')).join('') || '<div class="empty-state">暂无音色</div>'}</div></section>`;
  },
  mount: () => {
    qs('#newVoiceFromLibrary')?.addEventListener('click', () => { setSelectedEngine('rvc_applio'); navigate('dashboard'); });
    qs('#libraryVoiceCards')?.addEventListener('click', async (event) => {
      const deleteButton = event.target.closest('.voice-delete');
      if (deleteButton) {
        const name = deleteButton.dataset.name || '这个音色';
        if (!window.confirm(`删除音色「${name}」？`)) return;
        const body = new FormData();
        body.append('voice_profile_id', deleteButton.dataset.id || '');
        await api.post('/api/delete-voice', body);
        qs('#voiceProfile')?.querySelector(`option[value="${CSS.escape(deleteButton.dataset.id || '')}"]`)?.remove();
        if (state.selectedVoiceId === deleteButton.dataset.id) state.selectedVoiceId = '';
        navigate('voices');
        return;
      }
      const button = event.target.closest('.voice-select,.voice-train');
      if (!button) return;
      state.selectedVoiceId = button.dataset.id;
      qs('#voiceProfile').value = state.selectedVoiceId;
      if (button.classList.contains('voice-train')) {
        setSelectedEngine('rvc_applio');
        navigate('dashboard');
      } else {
        navigate('dashboard');
      }
    });
  },
};
