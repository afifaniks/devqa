"""
SecDevQA — Stage 3: grade model answers against the thread-grounded gold.

Implements the knowledge-type- and condition-aware protocol of research_plan_v6.md §3.4
(and methodology_review.md §5), in two tiers:

Tier 1 — deterministic, condition-aware hard-fact matching.
  Each hard fact is matched by identifier in the response, but scored only where it is
  KNOWABLE under the condition:
    * subject facts (cve_ids, ghsa_ids, cwe_ids, osv_ids) — gradeable under any condition;
    * internal/fix facts (fixed_versions, fix_prs, fix_commits, advisory_urls) — gradeable
      only under with-context/agent conditions; under no_context they are recorded as
      `not_gradeable`, never as misses.

Tier 2 — per-claim LLM judge.
  The judge sees the question, the thread-grounded gold answer, the grounding sources, and
  the anonymized candidate response. It decomposes the gold into atomic claims, verdicts
  each as yes/partial/no with a quoted supporting phrase, and lists hallucinated specifics
  (concrete factual assertions absent from / contradicting the gold). Overall outcome:
  correct / partial / incorrect; hallucination is reported separately, not collapsed into
  incorrect.

  NOTE (Phase 4, PLAN.md): the deferred diff oracle — resolving grounding_sources
  PR/commit refs to change diffs and giving them to the judge under with-context
  conditions — is not wired in yet. Judge ensembling and human κ calibration are also
  Phase 4.

Usage:
  python -m harness grade --answers harness/output/answers_openai-gpt-5.4-mini_no_context.jsonl
  python -m harness grade --answers ... --judge openai/gpt-5.4 --limit 5
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

from harness.llm import load_jsonl, chat_json

load_dotenv()

ROOT = Path(__file__).parent.parent
DEFAULT_PAIRS = ROOT / "dataset" / "security_benchmark_final.jsonl"
DEFAULT_JUDGE = "gpt-5.4"

# Hard-fact fields by knowability (methodology_review.md §5.1).
SUBJECT_FACT_FIELDS = ("cve_ids", "ghsa_ids", "cwe_ids", "osv_ids")
INTERNAL_FACT_FIELDS = ("fixed_versions", "fix_prs", "fix_commits", "advisory_urls")
# Conditions where the system had project/advisory access. Matched by prefix so
# selective-provision variants (snapshot_agent-no_advisory, snapshot_agent-only_code)
# are covered. TODO Phase 4: per-fact knowable_at_report temporal gate (PLAN.md).
CONTEXT_CONDITION_PREFIXES = ("single_artifact", "multi_artifact", "agent",
                              "snapshot_agent", "external_")


def is_context_condition(condition: str) -> bool:
    return str(condition).startswith(CONTEXT_CONDITION_PREFIXES)


# ---------------------------------------------------------------------------
# Tier 1 — deterministic, condition-aware hard-fact matching
# ---------------------------------------------------------------------------

def fact_in_text(field: str, value: str, text: str) -> bool:
    """Conservative identifier match with boundaries, per fact type."""
    t = text.lower()
    v = str(value).strip().lower()
    if not v:
        return False
    if field in ("cve_ids", "ghsa_ids", "cwe_ids", "osv_ids", "advisory_urls"):
        return v in t
    if field in ("fix_prs",):  # "#932" — require a PR-shaped mention, not a bare number
        num = v.lstrip("#")
        return re.search(rf"(?:#|pull/|pr[\s#]+){re.escape(num)}(?!\d)", t) is not None
    if field in ("fix_commits",):  # match on a >=7-char prefix of the SHA
        return len(v) >= 7 and v[:7] in t
    # versions and anything else: boundary match so 9.0.2 does not hit 19.0.21
    return re.search(rf"(?<![\w.]){re.escape(v)}(?![\w.])", t) is not None


def grade_hard_facts(hard_facts: dict, response: str, condition: str) -> list[dict]:
    results = []
    for field in SUBJECT_FACT_FIELDS + INTERNAL_FACT_FIELDS:
        for value in (hard_facts or {}).get(field, []) or []:
            internal = field in INTERNAL_FACT_FIELDS
            if internal and not is_context_condition(condition):
                status = "not_gradeable"          # unknowable under this condition
            else:
                status = "matched" if fact_in_text(field, value, response) else "missing"
            results.append({"field": field, "value": value, "status": status})
    return results


# ---------------------------------------------------------------------------
# Tier 2 — per-claim LLM judge
# ---------------------------------------------------------------------------

JUDGE_PROMPT = """\
You are grading an anonymous model's answer to a real developer security question, \
against a GOLD answer distilled from how the project maintainer actually answered. \
Verify SPECIFIC claims; do not rate holistic quality or style.

Procedure:
1. Decompose the GOLD answer into its atomic claims (a cause, a verdict, a \
user-actionable remediation, an affected/fixed version, a concrete identifier). 2-6 claims.
2. For each claim, verdict whether the RESPONSE conveys it: "yes" (clearly conveyed, \
possibly in different words), "partial" (incomplete or hedged but compatible), "no" \
(absent or contradicted). Quote the exact response phrase supporting your verdict \
("evidence"); empty string if verdict is "no".
3. List HALLUCINATIONS — condition-dependent:
   - Under no_context: specific factual assertions — concrete identifiers (CVE/GHSA), \
version numbers, PR/commit references, or definite project-specific verdicts — that are \
ABSENT from the gold answer AND not reasonable general security knowledge.
   - Under with-context/agent conditions (the model could READ the repository, issue \
tracker, and advisories): a specific assertion is a hallucination ONLY if it \
CONTRADICTS the gold answer or the question's premises. Extra verified-looking detail \
(identifiers, affected ranges, root-cause analysis) beyond a terse gold is expected \
tool-derived enrichment, NOT a hallucination.
   General advice or correct background knowledge is NEVER a hallucination. Quote each.
4. Overall: "correct" (all claims yes), "partial" (some yes/partial), "incorrect" \
(essentially none conveyed, or the central verdict contradicted).

CONDITION AWARENESS: the response was produced under the "{condition}" condition. \
Under no_context the model has NO access to this repository or its advisories, so do NOT \
penalize it for omitting project-internal identifiers (PR numbers, commit SHAs, exact \
release versions) — judge whether the substance (cause, verdict, remediation) is right. \
A claim that consists ONLY of such an internal identifier should be verdicted on its \
substance ("it is fixed" / "upgrade") rather than the identifier itself.

Output ONLY a JSON object:
{{
  "claims": [{{"claim": "...", "verdict": "yes"|"partial"|"no", "evidence": "..."}}],
  "hallucinations": [{{"assertion": "...", "evidence": "<quoted response phrase>"}}],
  "overall": "correct"|"partial"|"incorrect"
}}
"""

JUDGE_USER_TMPL = """\
QUESTION:
{question}

GOLD ANSWER (maintainer's stated resolution, distilled from the thread):
{gold}

GROUNDING SOURCES the gold rests on: {sources}
KNOWLEDGE TYPE: {ktype}

RESPONSE (anonymous model, condition={condition}):
{response}
"""


def judge_response(judge_model: str, pair: dict, response: str, condition: str) -> dict:
    system = JUDGE_PROMPT.format(condition=condition)
    user = JUDGE_USER_TMPL.format(
        question=pair["question"], gold=pair["answer"],
        sources=", ".join(pair.get("grounding_sources") or []) or "(none)",
        ktype=pair.get("knowledge_type"), condition=condition, response=response)
    out = chat_json(judge_model, system, user)
    claims = out.get("claims") or []
    halls = out.get("hallucinations") or []
    overall = out.get("overall")
    if overall not in ("correct", "partial", "incorrect"):
        verdicts = Counter(c.get("verdict") for c in claims)
        overall = ("correct" if claims and verdicts["yes"] == len(claims)
                   else "partial" if verdicts["yes"] or verdicts["partial"]
                   else "incorrect")
    return {"claims": claims, "hallucinations": halls, "overall": overall}


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def build_gold_index(pairs_path: Path) -> dict[str, tuple[dict, dict]]:
    index = {}
    for thread in load_jsonl(pairs_path):
        for p in thread.get("qa_pairs") or []:
            index[p["qid"]] = (thread, p)
    return index


def cross_check_flags(hard_results: list[dict], judge: dict) -> list[str]:
    """Deterministic-vs-judge consistency flags for human spot-check (plan §3.4)."""
    flags = []
    gradeable = [r for r in hard_results if r["status"] != "not_gradeable"]
    if gradeable and judge["overall"] == "correct" and all(r["status"] == "missing" for r in gradeable):
        flags.append("judge_correct_but_no_hard_fact_matched")
    if gradeable and judge["overall"] == "incorrect" and any(r["status"] == "matched" for r in gradeable):
        flags.append("judge_incorrect_but_hard_fact_matched")
    return flags


def run(answers_path: Path, pairs_path: Path, judge_model: str, output_path: Path | None,
        force: bool, limit: int | None) -> None:
    answers = [a for a in load_jsonl(answers_path) if not a.get("error")]
    if limit:
        answers = answers[:limit]
    gold = build_gold_index(pairs_path)
    if output_path is None:
        output_path = answers_path.parent / ("grades_" + answers_path.name.removeprefix("answers_"))

    done: set[str] = set()
    if output_path.exists() and not force:
        done = {r["qid"] for r in load_jsonl(output_path) if not r.get("error")}
        print(f"Resuming: {len(done)} already graded in {output_path}")

    print(f"Judge: {judge_model} | answers: {len(answers)} from {answers_path}")
    results, n_err = [], 0
    with open(output_path, "w" if force else "a", encoding="utf-8") as fh:
        for i, ans in enumerate(answers):
            qid = ans["qid"]
            if qid in done:
                continue
            if qid not in gold:
                print(f"[{i+1}/{len(answers)}] {qid} SKIP: not in {pairs_path}")
                continue
            thread, pair = gold[qid]
            condition = ans.get("condition", "no_context")
            print(f"[{i+1}/{len(answers)}] {qid} ...", end=" ", flush=True)
            rec = {"qid": qid, "thread_id": ans.get("thread_id"), "repo": ans.get("repo"),
                   "model": ans.get("model"), "condition": condition,
                   "knowledge_type": pair.get("knowledge_type"), "judge_model": judge_model}
            try:
                hard = grade_hard_facts(thread.get("hard_facts") or {}, ans["response"], condition)
                judge = judge_response(judge_model, pair, ans["response"], condition)
                rec["hard_facts"] = hard
                rec["judge"] = judge
                rec["hallucinated"] = bool(judge["hallucinations"])
                rec["outcome"] = judge["overall"]
                rec["flags"] = cross_check_flags(hard, judge)
                print(f"{rec['outcome']}{' HALLUC' if rec['hallucinated'] else ''}"
                      f"{' ' + ','.join(rec['flags']) if rec['flags'] else ''}")
            except Exception as exc:
                rec["error"] = str(exc)
                n_err += 1
                print(f"ERROR: {exc}")
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            results.append(rec)
            if i < len(answers) - 1:
                time.sleep(0.3)

    graded = [r for r in load_jsonl(output_path) if not r.get("error")]
    print(f"\nGraded: {len(graded)} total ({n_err} errors this run) → {output_path}")
    by = Counter((r["knowledge_type"], r["outcome"]) for r in graded)
    print("\nOutcome by knowledge type:")
    for (kt, oc), n in sorted(by.items()):
        print(f"  {kt:11s} {oc:10s} {n}")
    n_h = sum(1 for r in graded if r.get("hallucinated"))
    print(f"Hallucination rate: {n_h}/{len(graded)}")
    facts = [f for r in graded for f in r.get("hard_facts", []) if f["status"] != "not_gradeable"]
    if facts:
        m = sum(1 for f in facts if f["status"] == "matched")
        print(f"Hard-fact recall (gradeable under condition): {m}/{len(facts)}")
    flagged = sum(1 for r in graded if r.get("flags"))
    if flagged:
        print(f"Cross-check flags for human review: {flagged} records")


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage 3: grade model answers.")
    ap.add_argument("--answers", type=Path, required=True,
                    help="answers_*.jsonl produced by the harness (answer/agent/external)")
    ap.add_argument("--pairs", type=Path, default=DEFAULT_PAIRS,
                    help="benchmark jsonl with the gold answers (default: security_benchmark_final.jsonl)")
    ap.add_argument("--judge", default=DEFAULT_JUDGE,
                    help="LiteLLM judge model id (must differ from the candidate model)")
    ap.add_argument("--output", type=Path, default=None,
                    help="default: grades_<answers-name>.jsonl next to the answers file")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--force", action="store_true", help="Re-grade everything")
    args = ap.parse_args()
    run(args.answers, args.pairs, args.judge, args.output, args.force, args.limit)


if __name__ == "__main__":
    main()
