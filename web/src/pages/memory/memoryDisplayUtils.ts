export function formatDate(value?: string | null) {
  if (!value) return "暂无";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function formatPercent(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "暂无";
  return `${Math.round(value * 100)}%`;
}
