import { escapeHtml, formatNumber } from '../utils.js';

function labelFromMap(value, labels) {
  return labels[value] || value || '-';
}

export function resultFacts(data) {
  const metrics = data.metrics || {};
  const facts = [
    ['引擎', data.engine_id === 'rvc_applio' ? 'Applio RVC' : (data.engine_id === 'seedvc' ? 'Seed-VC' : data.engine_id || '-')],
    ['目标音色', metrics.voice_profile_name || '-'],
    ['歌曲', metrics.song_title || '上传歌曲'],
    ['生成目标', labelFromMap(metrics.rvc_preset, { stable_balanced: '自然稳定', clear_diction: '歌词更清楚', stronger_timbre_safe: '更像目标音色' })],
    ['人声修饰', labelFromMap(metrics.vocal_style, { neutral: '不额外修饰', close_intimate: '贴脸清晰', narrative_soft: '柔和抒情', low_thick: '温暖厚实', bright_pop: '明亮流行' })],
    ['混音风格', labelFromMap(metrics.mix_style, { natural: '自然', vocal_forward: '人声靠前', blend_with_backing: '融进伴奏' })],
    ['人声分离', labelFromMap(metrics.separation_mode, { standard: '标准', demucs_high_quality: '高质量', demucs_max_quality: '最高质量', ai_tolerant: 'AI歌容错' })],
    ['总用时', `${formatNumber(metrics.total_seconds, 1)} 秒`],
  ];
  return facts.map(([label, value]) => `<div class="result-fact"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join('');
}

export function resultNotices(data) {
  const diagnostics = data.metrics?.diagnostics || {};
  const issue = diagnostics.most_likely_issue;
  const suggestions = Array.isArray(diagnostics.suggestions) ? diagnostics.suggestions : [];
  const notices = [];
  const sourceSummary = data.metrics?.source_quality_summary;
  const problemCount = Number(data.metrics?.source_problem_segment_count || 0);
  if (sourceSummary) {
    const text = problemCount > 0 ? `源人声质量：${sourceSummary}，检测到 ${problemCount} 个可能沙哑或刺耳片段。` : `源人声质量：${sourceSummary}`;
    notices.push(['源人声质量', text]);
  }
  if (data.metrics?.auto_repair_variant_generated) notices.push(['AI 源修复版', '已生成一个修复版用于对比试听。']);
  if (data.metrics?.separation_fallback_used) notices.push(['人声分离', '已保护性回退到高质量分离，避免歌词变糊。']);
  if (issue && issue !== '未发现明显异常') notices.push(['问题提示', issue]);
  suggestions.slice(0, 2).forEach((text) => notices.push(['建议', text]));
  if (data.dry_vocal_download_wav_url || data.dry_vocal_download_mp3_url) notices.push(['干声输出', '已生成，可单独试听目标人声。']);
  return notices.map(([label, text]) => `<div class="result-notice"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(text)}</span></div>`).join('');
}

export function scoreItems(items) {
  return (items || []).map((item) => `<div class="score-item"><strong>${escapeHtml(item.label)}</strong><b>${escapeHtml(item.status || item.value || '-')}</b><span>${escapeHtml(item.detail || '')}</span></div>`).join('');
}
