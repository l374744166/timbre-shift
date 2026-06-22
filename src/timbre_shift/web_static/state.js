const savedEngine = window.localStorage?.getItem('timbreShift.engine') || 'seedvc';

export const state = {
  currentView: 'dashboard',
  selectedEngine: savedEngine === 'rvc_applio' ? 'rvc_applio' : 'seedvc',
  selectedVoiceId: '',
  selectedSongId: '',
  selectedVoiceModelId: '',
  progress: {},
  lastResult: null,
};

export function setSelectedEngine(engineId) {
  state.selectedEngine = engineId === 'rvc_applio' ? 'rvc_applio' : 'seedvc';
  window.localStorage?.setItem('timbreShift.engine', state.selectedEngine);
}
