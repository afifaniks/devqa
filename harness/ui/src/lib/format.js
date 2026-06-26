// Small pure formatting helpers.

export const age = s =>
  s == null ? "—"
  : s < 60 ? `${s}s ago`
  : s < 3600 ? `${Math.floor(s / 60)}m ago`
  : `${Math.floor(s / 3600)}h ago`;

export const pct = (n, total) =>
  total ? Math.min(100, Math.round((100 * n) / total)) : 0;

// The harness stamps processes with a compact UTC id like "20260626T021821Z".
// Render it as a readable local date-time, e.g. "Jun 26, 2026, 2:18 AM".
export function fmtStamp(s) {
  if (!s) return "—";
  const m = String(s).match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/);
  const d = m
    ? new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]))
    : new Date(s);
  if (isNaN(d)) return String(s);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", year: "numeric",
    hour: "numeric", minute: "2-digit",
  });
}
