export function AudioPlayer(id, label) {
  return `<div class="audio-block"><div class="audio-title">${label}</div><audio id="${id}" controls></audio></div>`;
}
