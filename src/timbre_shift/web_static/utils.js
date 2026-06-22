export const qs = (selector, root = document) => root.querySelector(selector);
export const qsa = (selector, root = document) => Array.from(root.querySelectorAll(selector));
export const escapeHtml = (value) => String(value ?? '').replace(/[&<>"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[char]));
export const formatNumber = (value, digits = 1) => value == null || Number.isNaN(Number(value)) ? '-' : Number(value).toFixed(digits);
export const formatDuration = (seconds) => seconds == null ? '时长未知' : `${Math.round(Number(seconds))}秒`;
export const selectedOptionData = (selectId) => {
  const select = qs(selectId);
  const option = select?.options?.[select.selectedIndex];
  return option ? { id: option.value, name: option.textContent.trim(), dataset: option.dataset } : { id: '', name: '', dataset: {} };
};
export const downloadName = (url, fallback) => url ? `${url}${url.includes('?') ? '&' : '?'}t=${Date.now()}` : fallback;
