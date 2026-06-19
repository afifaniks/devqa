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
