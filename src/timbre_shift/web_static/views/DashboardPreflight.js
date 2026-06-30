import { escapeHtml, qs } from '../utils.js';

function selectedOption(selector, value) {
  if (!value) return null;
  return qs(selector)?.querySelector(`option[value="${CSS.escape(value)}"]`) || null;
}

function buildPreflightItems({ isRvc, selectedVoiceId, selectedSongId, selectedVoiceModelId }) {
  const items = [];
  const voiceOption = selectedOption('#voiceProfile', selectedVoiceId);
  const songOption = selectedOption('#songLibrary', selectedSongId);
  const uploadedVoiceCount = qs('#voice')?.files?.length || 0;
  const uploadedSongCount = qs('#song')?.files?.length || 0;
  const sampleCount = Number(voiceOption?.dataset.sampleCount || 0);
  const modelCount = Number(voiceOption?.dataset.rvcModelCount || 0);
  const separationMode = qs('#separationMode')?.value || 'standard';
  const cleanupMode = qs('#preRvcCleanupMode')?.value || 'off';
  const outputMode = qs('#outputMode')?.value || 'full';

  if (selectedVoiceId || uploadedVoiceCount) {
    items.push({ level: 'ok', label: isRvc ? '目标音色库已选择' : '参考声音已准备', detail: selectedVoiceId ? (voiceOption?.textContent?.trim() || '已选择') : '将使用本次上传声音' });
  } else {
    items.push({ level: 'warn', label: isRvc ? '还没选择 RVC 音色库' : '还没选择参考声音', detail: isRvc ? '请先创建/选择音色库' : '请选择音色或上传参考声音' });
  }

  if (isRvc) {
    if (selectedVoiceModelId) {
      items.push({ level: 'ok', label: 'RVC 模型已指定', detail: '会使用当前选择的训练模型' });
    } else if (modelCount > 0) {
      items.push({ level: 'ok', label: 'RVC 模型可用', detail: `当前音色库有 ${modelCount} 个已训练模型，可自动选择` });
    } else {
      items.push({ level: 'warn', label: '还没有可用 RVC 模型', detail: sampleCount > 0 ? '已有素材，建议先训练模型再正式生成' : '请先添加训练素材并训练模型' });
    }
    items.push(sampleCount >= 3
      ? { level: 'ok', label: '训练素材较适合演示', detail: `${sampleCount} 条素材，音色稳定性更好` }
      : { level: 'warn', label: '训练素材偏少', detail: sampleCount > 0 ? `${sampleCount} 条素材可用，但建议补充多首干声` : '空音色库暂不适合正式生成' });
  } else if (sampleCount > 0 || uploadedVoiceCount) {
    items.push({ level: 'ok', label: 'Seed-VC 可快速试听', detail: '不需要训练模型，适合先听音色方向' });
  }

  if (selectedSongId || uploadedSongCount) {
    const songKind = songOption?.dataset.sourceKind || '';
    items.push(songKind === 'clean_vocal'
      ? { level: 'ok', label: '歌曲已是干净人声', detail: '可跳过人声分离，速度更快' }
      : { level: 'ok', label: '歌曲已准备', detail: selectedSongId ? (songOption?.textContent?.trim() || '已选择歌曲') : '将使用本次上传歌曲' });
  } else {
    items.push({ level: 'warn', label: '还没选择歌曲', detail: '请选择歌曲库或上传新歌曲' });
  }

  if (separationMode === 'standard' && cleanupMode === 'off') {
    items.push({ level: 'info', label: '普通歌曲配置', detail: '普通干净歌曲推荐这样；AI 生成歌建议切到高质量分离或源人声修复' });
  } else if (separationMode === 'demucs_max_quality') {
    items.push({ level: 'warn', label: '最高质量分离较慢', detail: '适合疑难歌曲，演示前请预留时间' });
  } else {
    items.push({ level: 'ok', label: '容错设置已开启', detail: '更适合 AI 歌、噪音歌或干声不干净的素材' });
  }

  if (outputMode === 'variants') {
    items.push({ level: 'info', label: '会生成对比版本', detail: '可试听稳定版、清晰版、音色更像版后再选最终版本' });
  }

  return items;
}

function itemHtml(item) {
  const levelText = item.level === 'ok' ? '通过' : (item.level === 'warn' ? '注意' : '建议');
  return `<div class="preflight-item ${escapeHtml(item.level)}"><span>${levelText}</span><div><strong>${escapeHtml(item.label)}</strong><p>${escapeHtml(item.detail)}</p></div></div>`;
}

export function preflightPanel() {
  return `<section class="preflight-panel" id="preflightPanel"><div class="section-head-row"><div><h3>生成前检查</h3><p class="muted">点生成前先看这里，避免忘选模型、歌曲或素材。</p></div><span class="status-badge" id="preflightStatus">待检查</span></div><div id="preflightChecklist" class="preflight-list"></div></section>`;
}

export function renderPreflight(context) {
  const target = qs('#preflightChecklist');
  if (!target) return [];
  const items = buildPreflightItems(context);
  target.innerHTML = items.map(itemHtml).join('');
  const hasWarn = items.some((item) => item.level === 'warn');
  const status = qs('#preflightStatus');
  if (status) {
    status.textContent = hasWarn ? '有注意项' : '可以生成';
    status.className = `status-badge ${hasWarn ? 'warn' : 'ok'}`;
  }
  return items;
}
