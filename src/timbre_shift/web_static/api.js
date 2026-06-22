async function parse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || data.message || '请求失败');
  return data;
}

export const api = {
  check: () => fetch('/api/check').then(parse),
  progress: () => fetch('/api/progress').then(parse),
  history: () => fetch('/api/history').then(parse),
  latestResult: () => fetch('/api/latest-result').then(parse),
  voiceModels: (voiceId, engineId) => fetch(`/api/voice-models?voice_id=${encodeURIComponent(voiceId || '')}&engine_id=${encodeURIComponent(engineId || 'rvc_applio')}`).then(parse),
  voiceSamples: (voiceId) => fetch(`/api/voice-samples?voice_id=${encodeURIComponent(voiceId || '')}`).then(parse),
  voicePreference: (voiceId) => fetch(`/api/voice-preference?voice_id=${encodeURIComponent(voiceId || '')}`).then(parse),
  post: (url, body) => fetch(url, { method: 'POST', body }).then(parse),
  generate: (body) => fetch('/api/generate', { method: 'POST', body }).then(parse),
  cancelTask: () => fetch('/api/cancel-task', { method: 'POST', body: new FormData() }).then(parse),
};
