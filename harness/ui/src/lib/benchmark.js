// Helpers for the benchmark browser.

// Some fields (grounding_sources, leak_flags) arrive as real arrays or as a stringified
// Python list ("['a', 'b']"). Normalize both to an array of strings for display.
export function asItems(v) {
  if (Array.isArray(v)) return v.filter(x => x != null && x !== "");
  if (v == null) return [];
  const s = String(v).trim();
  if (s.startsWith("[") && s.endsWith("]")) {
    return s.slice(1, -1)
      .split(",")
      .map(x => x.trim().replace(/^['"]|['"]$/g, ""))
      .filter(Boolean);
  }
  return s ? [s] : [];
}

// hard_facts dict field → short label.
export const HF_LABEL = {
  cve_ids: "CVE", ghsa_ids: "GHSA", cwe_ids: "CWE", osv_ids: "OSV",
  fixed_versions: "fixed", fix_prs: "fix PR", fix_commits: "fix commit",
  advisory_urls: "advisory",
};

// Identifier-bearing fields render teal (verifiable IDs); the rest are quieter.
export const HF_ID_FIELDS = new Set(["cve_ids", "ghsa_ids", "cwe_ids", "osv_ids"]);

export const ROLE_COLOR = {
  maintainer: "teal", contributor: "azure", commenter: "gray", op_self: "violet",
};

export const KT_COLOR = { grounded: "teal", parametric: "violet" };

// The "grounded" knowledge type is surfaced to readers as "contextual" (the data
// value stays "grounded" — eval/grading depend on it). Use ktLabel() everywhere a
// knowledge_type is shown.
export const KT_LABEL = { grounded: "contextual", parametric: "parametric" };
export const ktLabel = kt => KT_LABEL[kt] || kt || "";

// Flatten a hard_facts dict to [{field, label, value, isId}] chips.
export function hardFactChips(hf) {
  const out = [];
  for (const [field, values] of Object.entries(hf || {})) {
    for (const value of values || []) {
      out.push({ field, label: HF_LABEL[field] || field, value, isId: HF_ID_FIELDS.has(field) });
    }
  }
  return out;
}

export const totalHardFacts = hf =>
  Object.values(hf || {}).reduce((a, v) => a + (v?.length || 0), 0);

// A rubric criterion's source_loc is an internal provenance token
// (e.g. "answer_reply", "fix_diff:coders/heic.c"). Turn it into something a reader
// understands, and flag whether the quoted span is *external evidence* (artifact the
// reader can't see elsewhere on the page) vs. text already shown in the gold answer.
const SOURCE_LABEL = {
  answer_reply: "Maintainer's answer",
  gold_answer: "Gold answer",
  hard_facts: "Verified fact",
  fix_diff: "Fix diff",
  commit: "Commit",
  advisory: "Advisory",
  issues: "Issue thread",
  prs: "PR thread",
};
// kinds whose quoted span duplicates the gold answer already rendered above
const ANSWER_SIDE = new Set(["answer_reply", "gold_answer"]);

export function sourceInfo(loc) {
  const raw = String(loc || "").trim();
  const [kind, ...rest] = raw.split(":");
  const detail = rest.join(":").trim();
  const base = SOURCE_LABEL[kind] || kind || "source";
  return {
    label: detail ? `${base} · ${detail}` : base,
    external: !ANSWER_SIDE.has(kind) && !!kind,   // true → show quote as evidence
  };
}
