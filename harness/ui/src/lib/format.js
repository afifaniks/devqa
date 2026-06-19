// Small pure formatting helpers.

export const age = s =>
  s == null ? "—"
  : s < 60 ? `${s}s ago`
  : s < 3600 ? `${Math.floor(s / 60)}m ago`
  : `${Math.floor(s / 3600)}h ago`;

export const pct = (n, total) =>
  total ? Math.min(100, Math.round((100 * n) / total)) : 0;
