import { outcomeOf } from "./outcomes.js";

// Distinct chart colors per run, assigned by selection order (Mantine color refs).
export const RUN_PALETTE = [
  "azure.5", "violet.5", "teal.5", "pink.5", "orange.5", "cyan.5", "grape.5", "lime.5",
];

// Aggregate the compare rows into per-run metrics for the stats panel. Pure: it reads
// only what /api/compare already returns (outcome, hallucinated, hard_facts, tool calls,
// knowledge_type), so it recomputes instantly as filters change.
export function computeStats(rows, runs) {
  const per = {};
  runs.forEach((rn, i) => {
    per[rn] = {
      name: rn, alias: `R${i + 1}`, color: RUN_PALETTE[i % RUN_PALETTE.length],
      answered: 0, graded: 0, correct: 0, partial: 0, incorrect: 0, error: 0,
      hallucinated: 0, factsMatched: 0, factsGradeable: 0,
      toolCalls: 0, withTools: 0, toolByGroup: {}, byKT: {},
    };
  });

  for (const row of rows) {
    const kt = row.knowledge_type || "unknown";
    for (const rn of runs) {
      const c = row.cells[rn];
      if (!c) continue;
      const p = per[rn];
      p.answered++;
      const o = outcomeOf(c);
      if (o === "error") { p.error++; continue; }
      if (c.graded) {
        p.graded++;
        p[o] = (p[o] || 0) + 1; // correct / partial / incorrect
        if (c.hallucinated) p.hallucinated++;
        const k = (p.byKT[kt] ||= { graded: 0, correct: 0, partial: 0 });
        k.graded++;
        if (o === "correct") k.correct++;
        else if (o === "partial") k.partial++;
      }
      for (const f of c.hard_facts || []) {
        if (f.status === "matched") { p.factsMatched++; p.factsGradeable++; }
        else if (f.status === "missing") p.factsGradeable++;
      }
      if (c.n_tool_calls != null) { p.toolCalls += c.n_tool_calls; p.withTools++; }
      for (const [g, n] of Object.entries(c.tool_calls_by_group || {})) {
        p.toolByGroup[g] = (p.toolByGroup[g] || 0) + n;
      }
    }
  }

  for (const p of Object.values(per)) {
    p.accuracy = p.graded ? p.correct / p.graded : 0;                  // strict
    p.score = p.graded ? (p.correct + 0.5 * p.partial) / p.graded : 0; // partial credit
    p.hallucRate = p.graded ? p.hallucinated / p.graded : 0;
    p.factMatchRate = p.factsGradeable ? p.factsMatched / p.factsGradeable : null;
    p.avgTools = p.withTools ? p.toolCalls / p.withTools : null;
  }
  return per;
}

export const knowledgeTypes = rows =>
  [...new Set(rows.map(r => r.knowledge_type).filter(Boolean))].sort();

export const toolGroups = per =>
  [...new Set(Object.values(per).flatMap(p => Object.keys(p.toolByGroup)))].sort();

export const pct1 = x => (x == null ? null : Math.round(x * 1000) / 10); // 0..100, 1dp
