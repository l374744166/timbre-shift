export function ProgressSteps(items, active = 0) {
  return `<div class="step-list">${items.map((item, index) => `<div class="step-pill ${index === active ? 'active' : ''}"><span>${index + 1}</span>${item}</div>`).join('')}</div>`;
}
