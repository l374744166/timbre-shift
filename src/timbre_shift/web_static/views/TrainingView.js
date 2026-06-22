import { api } from '../api.js';
import { qs } from '../utils.js';
export const TrainingView = {
  render: () => `<section class="view-panel"><div class="view-head"><div><h2>RVC 训练</h2><p>单独管理数据集准备、训练和模型保存</p></div></div><div class="train-flow"><div class="step-card">1. 选择音色<select id="trainingVoice">${qs('#voiceProfile').innerHTML}</select></div><div class="step-card">2. 检查素材<div id="voiceSampleList" class="sample-list">选择音色后显示素材明细</div></div><div class="step-card">3. 准备数据集<button class="secondary" id="prepareApplioButton" type="button">准备数据集</button></div><div class="step-card">4. 开始训练<select id="applioEpochs"><option value="10">10 轮</option><option value="40">40 轮</option><option value="80">80 轮</option></select><button id="trainApplioButton" type="button">开始训练</button></div><div class="step-card">5. 训练完成<div id="applioTrainMessage" class="message">模型已保存后可回工作台生成歌曲</div></div></div></section>`,
  mount: () => {
    const voice = qs('#trainingVoice');
    const loadSamples = async () => { const data = await api.voiceSamples(voice.value); qs('#voiceSampleList').innerHTML = (data.samples || []).map((sample) => `<div class="sample-row"><strong>${sample.name}</strong><span>${sample.source_label}</span></div>`).join('') || '<div class="muted">暂无素材</div>'; };
    voice.addEventListener('change', loadSamples); loadSamples();
    qs('#prepareApplioButton').addEventListener('click', async () => { const body = new FormData(); body.append('voice_profile_id', voice.value); qs('#applioTrainMessage').textContent = '正在准备数据集...'; try { const data = await api.post('/api/applio-prepare', body); qs('#applioTrainMessage').textContent = data.message || '数据集已准备'; } catch (error) { qs('#applioTrainMessage').textContent = error.message; } });
    qs('#trainApplioButton').addEventListener('click', async () => { const body = new FormData(); body.append('voice_profile_id', voice.value); body.append('epochs', qs('#applioEpochs').value); qs('#applioTrainMessage').textContent = '正在训练...'; try { const data = await api.post('/api/applio-train', body); qs('#applioTrainMessage').textContent = data.message || '模型已保存'; } catch (error) { qs('#applioTrainMessage').textContent = error.message; } });
  },
};
