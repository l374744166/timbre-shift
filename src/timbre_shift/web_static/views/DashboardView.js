import { api } from '../api.js';
import { state } from '../state.js';
import { qs, qsa, selectedOptionData, escapeHtml, formatNumber } from '../utils.js';
import { navigate } from '../router.js';
import { VoiceCard } from '../components/VoiceCard.js';
import { SongCard } from '../components/SongCard.js';
import { ProgressSteps } from '../components/ProgressSteps.js';
import { ResultCard } from '../components/ResultCard.js';
import { VariantCard } from '../components/VariantCard.js';

function voiceCards() {
  const select = qs('#voiceProfile');
  return Array.from(select.options).filter((option) => option.value).map((option) => VoiceCard(option, state.selectedVoiceId)).join('') || '<div class="empty-state">还没有音色，先上传或新建一个。</div>';
}
function songCards() {
  const select = qs('#songLibrary');
  return Array.from(select.options).filter((option) => option.value).map((option) => SongCard(option, state.selectedSongId)).join('') || '<div class="empty-state">还没有歌曲库记录，可以直接上传新歌曲。</div>';
}

export const DashboardView = {
  render: () => `<form id="form" class="dashboard-form">
    <section class="view-panel"><div class="view-head"><div><h2>工作台</h2><p>四步完成本地 AI 音色转换</p></div><span class="status-badge ok">演示模式友好</span></div>${ProgressSteps(['转换方式', '目标音色', '歌曲', '生成设置'], 0)}</section>
    <section class="step-section"><h3>Step 1：选择转换方式</h3><div class="choice-grid">
      <label class="choice-card"><input type="radio" name="engine_id" value="seedvc" ${state.selectedEngine === 'seedvc' ? 'checked' : ''}><strong>Seed-VC 快速试听</strong><span>适合 30 秒声音，不需要训练，快速听效果</span></label>
      <label class="choice-card"><input type="radio" name="engine_id" value="rvc_applio" ${state.selectedEngine === 'rvc_applio' ? 'checked' : ''}><strong>Applio RVC 正式生成</strong><span>适合已训练音色模型，多首歌长期使用</span></label>
    </div></section>
    <section class="step-section"><h3>Step 2：选择目标音色</h3><div class="resource-grid" id="voiceCards">${voiceCards()}</div>
      <div class="upload-strip"><input id="voice" name="voice" type="file" accept="audio/*" multiple><input id="voiceName" name="voice_name" placeholder="新音色名称"><button class="secondary" id="saveVoiceButton" type="button">保存音色</button><button class="secondary" id="addVoiceSampleButton" type="button">添加素材</button></div><div class="message" id="voiceSaveMessage"></div></section>
    <section class="step-section"><h3>Step 3：选择歌曲</h3><div class="resource-grid" id="songCards">${songCards()}</div><div class="upload-strip"><input id="song" name="song" type="file" accept="audio/*"><span class="muted">也可以上传干净人声，高级设置里选择源人声清理。</span></div></section>
    <section class="step-section"><h3>Step 4：生成设置</h3><div class="settings-grid">
      <label>生成目标<select id="rvcPreset" name="rvc_preset"><option value="stable_balanced">自然稳定</option><option value="clear_diction">歌词更清楚</option><option value="stronger_timbre_safe">更像目标音色</option></select></label>
      <label>人声修饰<select id="vocalStyle" name="vocal_style"><option value="neutral">不额外修饰</option><option value="close_intimate">贴脸清晰</option><option value="narrative_soft">柔和抒情</option><option value="low_thick">温暖厚实</option><option value="bright_pop">明亮流行</option></select></label>
      <label>输出<select id="outputMode"><option value="full">完整歌曲</option><option value="dry">干声</option><option value="variants">生成对比版本</option></select></label>
    </div>
    <details class="details-panel"><summary>高级设置</summary><div class="settings-grid"><label>源人声清理<select id="preRvcCleanupMode" name="pre_rvc_cleanup_mode"><option value="off">关闭</option><option value="standard">标准</option><option value="strong">强力</option></select></label><label>咬字增强<select id="dictionMode" name="diction_mode"><option value="off">关闭</option><option value="light" selected>轻微</option><option value="medium">中等</option><option value="strong">强</option></select></label><label>音色记忆库<select id="rvcIndexRate" name="rvc_index_rate"><option value="0">关闭</option><option value="0.25">轻度</option><option value="0.45">中度</option></select></label><label>混音风格<select id="mixStyle" name="mix_style"><option value="natural">自然</option><option value="vocal_forward">人声靠前</option><option value="blend_with_backing">融进伴奏</option></select></label><label class="check"><input id="allowExperimentalIndex" name="allow_experimental_index" type="checkbox">开启实验音色记忆库</label><label class="check"><input id="generateVariants" name="generate_variants" type="checkbox">生成对比版本</label></div></details>
    <input type="hidden" name="mode" value="m2max_hq_30"><input type="hidden" id="voiceModel" name="voice_model_id"><input type="hidden" name="song_id" id="songIdField"><input type="hidden" name="voice_profile_id" id="voiceIdField"><input type="hidden" name="voice_source_type" value="clean_voice"><input type="hidden" name="mix_style" value="natural">
    <div class="action-bar"><button id="submit" type="submit">开始生成</button><div id="message" class="message"></div></div></section>${ResultCard()}</form>`,
  mount: () => {
    qsa('input[name="engine_id"]').forEach((input) => input.addEventListener('change', () => { state.selectedEngine = input.value; }));
    qs('#voiceCards')?.addEventListener('click', (event) => { const button = event.target.closest('.voice-select,.voice-train'); if (!button) return; state.selectedVoiceId = button.dataset.id; qs('#voiceProfile').value = state.selectedVoiceId; qs('#voiceIdField').value = state.selectedVoiceId; if (button.classList.contains('voice-train')) navigate('training'); else navigate('dashboard'); });
    qs('#songCards')?.addEventListener('click', (event) => { const button = event.target.closest('.song-select'); if (!button) return; state.selectedSongId = button.dataset.id; qs('#songLibrary').value = state.selectedSongId; qs('#songIdField').value = state.selectedSongId; navigate('dashboard'); });
    qs('#outputMode')?.addEventListener('change', (event) => { qs('#generateVariants').checked = event.target.value === 'variants'; });
    qs('#saveVoiceButton')?.addEventListener('click', async () => { const body = new FormData(); const files = qs('#voice').files; Array.from(files).forEach((file) => body.append('voice', file)); body.append('voice_name', qs('#voiceName').value || '未命名音色'); body.append('voice_source_type', 'clean_voice'); qs('#voiceSaveMessage').textContent = '正在保存音色...'; try { const data = await api.post(state.selectedEngine === 'rvc_applio' ? '/api/create-voice-profile' : '/api/save-voice', body); qs('#voiceSaveMessage').textContent = data.message || '已保存'; } catch (error) { qs('#voiceSaveMessage').textContent = error.message; } });
    qs('#addVoiceSampleButton')?.addEventListener('click', async () => { const body = new FormData(); Array.from(qs('#voice').files).forEach((file) => body.append('voice', file)); body.append('voice_name', qs('#voiceName').value || '声音素材'); body.append('voice_profile_id', state.selectedVoiceId); body.append('voice_source_type', 'clean_voice'); qs('#voiceSaveMessage').textContent = '正在添加素材...'; try { const data = await api.post('/api/add-voice-sample', body); qs('#voiceSaveMessage').textContent = data.message || '素材已添加'; } catch (error) { qs('#voiceSaveMessage').textContent = error.message; } });
    qs('#form').addEventListener('submit', async (event) => { event.preventDefault(); qs('#message').textContent = '正在生成...'; const body = new FormData(qs('#form')); body.set('engine_id', state.selectedEngine); body.set('voice_profile_id', state.selectedVoiceId); body.set('song_id', state.selectedSongId); try { const data = await api.generate(body); renderResult(data); qs('#message').textContent = data.message || '生成完成'; } catch (error) { qs('#message').textContent = error.message; } });
  },
};

function renderResult(data) {
  state.lastResult = data;
  const result = qs('#result');
  result.classList.remove('hidden');
  qs('#resultSummary').textContent = `${data.engine_id || '-'} · ${data.render_mode || '-'} · ${formatNumber(data.metrics?.total_seconds, 1)}秒`;
  const mp3 = data.download_mp3_url || data.download_url;
  const wav = data.download_wav_url || data.download_url;
  qs('#player').src = mp3 ? `${mp3}?t=${Date.now()}` : '';
  qs('#download').href = mp3 || '#';
  qs('#download').download = data.mp3_filename || 'final.mp3';
  qs('#downloadWav').href = wav || '#';
  qs('#downloadWav').download = data.wav_filename || 'final.wav';
  qs('#dryVocalPlayer').src = data.dry_vocal_download_mp3_url ? `${data.dry_vocal_download_mp3_url}?t=${Date.now()}` : '';
  qs('#downloadDryVocal').href = data.dry_vocal_download_mp3_url || '#';
  qs('#downloadDryVocalWav').href = data.dry_vocal_download_wav_url || '#';
  qs('#scorecard').innerHTML = (data.scorecard || []).map((item) => `<div class="score-item"><strong>${escapeHtml(item.label)}</strong><span>${escapeHtml(item.value)}</span></div>`).join('');
  qs('#metrics').textContent = JSON.stringify(data.metrics || {}, null, 2);
  qs('#variants').innerHTML = (data.variants || []).map(VariantCard).join('');
}
