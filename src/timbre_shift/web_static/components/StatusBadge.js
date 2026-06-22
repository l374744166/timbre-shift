export function StatusBadge(label, tone = 'neutral') {
  return `<span class="status-badge ${tone}">${label}</span>`;
}
