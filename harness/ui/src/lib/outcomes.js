// The verdict vocabulary — the heart of the harness's visual language.
// Every prediction resolves to exactly one of these outcomes.

export const OUTCOME_ORDER = ["correct", "partial", "incorrect", "error", "ungraded"];

// Resolve an answer+grade cell to a single outcome label.
export function outcomeOf(cell) {
  if (!cell) return null;
  if (cell.error) return "error";
  if (cell.graded) return cell.outcome || "ungraded";
  return "ungraded";
}

// Judge per-claim verdicts use yes / partial / no → a verdict color.
export const claimColor = v =>
  v === "yes" ? "teal" : v === "partial" ? "yellow" : "red";

// Dominant graded outcome among a set of cells (drives the run verdict spine).
export function dominantOutcome(cells) {
  const counts = {};
  for (const c of cells) {
    const o = outcomeOf(c);
    if (o && o !== "ungraded") counts[o] = (counts[o] || 0) + 1;
  }
  let best = null, n = 0;
  for (const [o, c] of Object.entries(counts)) if (c > n) { best = o; n = c; }
  return best;
}
