import { escapeHtml, qs } from '../utils.js';

function tipsForError(message) {
  const text = String(message || '').toLowerCase();
  const tips = [];
  if (text.includes('model') || text.includes('模型') || text.includes('.pth') || text.includes('applio rvc')) {
    tips.push('RVC 模型可能没有准备好：请在音色详情或训练区确认已有“ready/已训练”模型。');
    tips.push('如果刚训练完成但找不到模型，建议重新打开音色详情确认模型列表，再选择生成。');
  }
  if (text.includes('ffmpeg') || text.includes('sigpipe') || text.includes('audio') || text.includes('音频') || text.includes('wav') || text.includes('mp3')) {
    tips.push('音频文件可能不太标准：建议换成 WAV/MP3，或重新导出一版再上传。');
  }
  if (text.includes('demucs') || text.includes('separation') || text.includes('分离')) {
    tips.push('人声分离失败或干声太脏：建议把“人声分离质量”切到高质量，AI 歌再配合“AI 生成歌曲修复”。');
  }
  if (text.includes('seed') || text.includes('mps') || text.includes('memory') || text.includes('内存')) {
    tips.push('换声占用资源较高：可以先用短片段/Seed-VC 快速试听，再做完整歌曲。');
  }
  if (!tips.length) {
    tips.push('先检查是否已选择音色和歌曲；如果是 AI 生成歌或噪音歌，优先尝试高质量分离。');
    tips.push('如果同一首歌反复失败，可以换一个更干净的源歌测试，确认模型本身是否正常。');
  }
  return tips;
}

export function errorAdvicePanel() {
  return `<div id="errorAdvice" class="error-advice hidden"></div>`;
}

export function showErrorAdvice(error) {
  const target = qs('#errorAdvice');
  if (!target) return;
  const message = error?.message || String(error || '生成失败');
  const tips = tipsForError(message);
  target.classList.remove('hidden');
  target.innerHTML = `<strong>生成失败建议</strong><p>${escapeHtml(message)}</p><ul>${tips.map((tip) => `<li>${escapeHtml(tip)}</li>`).join('')}</ul>`;
}

export function clearErrorAdvice() {
  const target = qs('#errorAdvice');
  if (!target) return;
  target.classList.add('hidden');
  target.innerHTML = '';
}
