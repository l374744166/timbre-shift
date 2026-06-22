import { qs } from '../utils.js';
import { VoiceCard } from '../components/VoiceCard.js';

export const VoiceLibraryView = {
  render: () => {
    const options = Array.from(qs('#voiceProfile').options).filter((option) => option.value);
    return `<section class="view-panel"><div class="view-head"><div><h2>音色库</h2><p>资源卡片管理目标音色、素材和训练状态</p></div><button>新建音色</button></div><div class="toolbar"><input placeholder="搜索音色"><select><option>全部</option><option>已训练</option><option>未训练</option><option>素材不足</option></select></div><div class="resource-grid">${options.map((option) => VoiceCard(option)).join('') || '<div class="empty-state">暂无音色</div>'}</div></section>`;
  },
  mount: () => {},
};
