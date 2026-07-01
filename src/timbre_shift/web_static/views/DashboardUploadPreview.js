import { escapeHtml, qs } from '../utils.js';

function fileSize(bytes) {
  const size = Number(bytes || 0);
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  if (size >= 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${size} B`;
}

function fileRows(files) {
  return Array.from(files || []).slice(0, 6).map((file) => `<li>${escapeHtml(file.name)} <span>${fileSize(file.size)}</span></li>`).join('');
}

function moreText(files) {
  const count = Number(files?.length || 0);
  return count > 6 ? `<p class="muted">还有 ${count - 6} 个文件未展开显示</p>` : '';
}

export function uploadPreview(id) {
  return `<div id="${id}" class="upload-preview hidden"></div>`;
}

export function renderVoiceUploadPreview({ isRvc }) {
  const target = qs('#voiceUploadPreview');
  if (!target) return;
  const files = qs('#voice')?.files;
  if (!files?.length) {
    target.classList.add('hidden');
    target.innerHTML = '';
    return;
  }
  const sourceType = qs('#voiceSourceType')?.value || 'clean_voice';
  const action = isRvc ? '会添加到当前 RVC 音色库作为训练素材' : '会保存为 Seed-VC 参考声音';
  const separation = sourceType === 'mixed_voice' ? '带伴奏上传：系统会先做人声分离' : '干净人声上传：不会额外做人声分离';
  target.classList.remove('hidden');
  target.innerHTML = `<strong>已选择 ${files.length} 个声音文件</strong><p>${escapeHtml(separation)}；${escapeHtml(action)}。</p><ul>${fileRows(files)}</ul>${moreText(files)}`;
}

export function renderSongUploadPreview() {
  const target = qs('#songUploadPreview');
  if (!target) return;
  const files = qs('#song')?.files;
  if (!files?.length) {
    target.classList.add('hidden');
    target.innerHTML = '';
    return;
  }
  const mode = qs('#separationMode')?.value || 'standard';
  const modeText = mode === 'demucs_max_quality' ? '最高质量分离，速度较慢' : (mode === 'demucs_high_quality' ? '高质量分离，适合 AI 歌优先尝试' : '标准分离，适合普通歌曲');
  target.classList.remove('hidden');
  target.innerHTML = `<strong>已选择待生成歌曲</strong><p>${escapeHtml(modeText)}。如果上传的是干净人声，可以在高级设置里关闭不必要清理。</p><ul>${fileRows(files)}</ul>${moreText(files)}`;
}
