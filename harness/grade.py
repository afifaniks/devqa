"""
SecDevQA — Stage 3: grade model answers against the frozen, per-item RUBRIC.

This implements grading_scheme_final.md §3–§5, with one deliberate simplification:
a **single LLM judge** (not a jury) for now. Each item carries a human-verified rubric
of criteria (released in dataset/security_benchmark_release.jsonl, embedded per qa_pair).
Grading checks **each rubric criterion separately** against the candidate response.

Per criterion the judge returns met / partial / not_met (1 / 0.5 / 0) with a quoted
supporting span. Criteria roll up **per axis**:

  correctness_score  = mean over GRADEABLE correctness criteria   (the primary outcome)
  completeness_score = mean over GRADEABLE completeness criteria  (secondary coverage)
  outcome ∈ {correct ≥ τ_hi, partial ∈ [τ_lo, τ_hi), incorrect < τ_lo}  from correctness

Temporal gating (§5): a criterion with knowable_at_report == False names a future fact;
it is dropped from the denominator under every non-oracle condition (recorded
not_gradeable, never a miss). A separate hallucination pass flags only response claims
that directly CONTRADICT the gold answer / a rubric criterion / the question's premises —
unstated-but-plausible detail is not a hallucination (freeform answers may add correct
extra content). Reported beside the score, never subtracted.

A lightweight deterministic hard-fact match is retained as an auxiliary cross-check only.

Usage:
  python -m harness grade --answers harness/output/answers_<run>.jsonl
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
# Grading needs the embedded rubric, so the released benchmark is the gold source.
DEFAULT_PAIRS = ROOT / "dataset" / "security_benchmark_release.jsonl"
DEFAULT_JUDGE = "gpt-5.4"

# Outcome thresholds on the correctness score (pre-registered; calibrate against the
# human sample in grading_scheme_final.md §6 before reporting).
TAU_HI = 0.70   # ≥ → correct
TAU_LO = 0.30   # ≥ → partial, else incorrect
VERDICT_SCORE = {"met": 1.0, "partial": 0.5, "not_met": 0.0}

# Conditions where the system had project/advisory access (affects hard-fact aux +
# the judge's condition-aware hallucination rule). Matched by prefix.
CONTEXT_CONDITION_PREFIXES = ("single_artifact", "multi_artifact", "agent",
                              "snapshot_agent", "external_", "oracle")


def is_context_condition(condition: str) -> bool:
    return str(condition).startswith(CONTEXT_CONDITION_PREFIXES)


def line_gradeable(criterion: dict, condition: str) -> bool:
    """A criterion naming a future fact (knowable_at_report == False) is gradeable
    only under the oracle condition; otherwise it drops out of the denominator."""
    if str(condition) == "oracle":
        return True
    return criterion.get("knowable_at_report", True) is not False


# ---------------------------------------------------------------------------
# Auxiliary deterministic hard-fact match (cross-check only, not the score)
# ---------------------------------------------------------------------------

SUBJECT_FACT_FIELDS = ("cve_ids", "ghsa_ids", "cwe_ids", "osv_ids")
INTERNAL_FACT_FIELDS = ("fixed_versions", "fix_prs", "fix_commits", "advisory_urls")


def fact_in_text(field: str, value: str, text: str) -> bool:
    """Conservative identifier match with boundaries, per fact type."""
    t = text.lower()
    v = str(value).strip().lower()
    if not v:
        return False
    if field in ("cve_ids", "ghsa_ids", "cwe_ids", "osv_ids", "advisory_urls"):
        return v in t
    if field in ("fix_prs",):
        num = v.lstrip("#")
        return re.search(rf"(?:#|pull/|pr[\s#]+){re.escape(num)}(?!\d)", t) is not None
    if field in ("fix_commits",):
        return len(v) >= 7 and v[:7] in t
    return re.search(rf"(?<![\w.]){re.escape(v)}(?![\w.])", t) is not None


def grade_hard_facts(hard_facts: dict, response: str, condition: str) -> list[dict]:
    results = []
    for field in SUBJECT_FACT_FIELDS + INTERNAL_FACT_FIELDS:
        for value in (hard_facts or {}).get(field, []) or []:
            internal = field in INTERNAL_FACT_FIELDS
            if internal and not is_context_condition(condition):
                status = "not_gradeable"
            else:
                status = "matched" if fact_in_text(field, value, response) else "missing"
            results.append({"field": field, "value": value, "status": status})
    return results


# ---------------------------------------------------------------------------
# Rubric judge — one LLM call, every criterion scored separately
# ---------------------------------------------------------------------------

JUDGE_PROMPT = """\
You are grading an anonymous model's answer to a real developer security question against \
a fixed RUBRIC. Each rubric criterion is one specific thing a correct answer should convey; \
the criteria were written by experts from the issue thread, the fix diff, and the advisory. \
A GOLD answer (the maintainer's distilled resolution) is given as reference. Judge SPECIFIC \
content, not style or holistic quality.

For EACH numbered criterion decide how the RESPONSE satisfies it:
  - "met": the response clearly conveys the criterion's content (wording may differ).
  - "partial": partially, incompletely, or hedged, but compatible and not wrong.
  - "not_met": absent from the response, or contradicted by it.
Quote the exact response phrase you relied on in "evidence" (empty string if not_met), and \
give a one-line "reason". An answer matching one of the ACCEPTABLE ALTERNATIVES satisfies \
the criterion it pertains to.

Then list HALLUCINATIONS. This is a FREEFORM answer, so a fact is NOT a hallucination \
merely because the gold/rubric does not mention it. Flag an \
assertion ONLY when it directly CONTRADICTS / opposes something stated in the gold answer, \
a rubric criterion, or the question's premises (e.g. claims "not affected" when the gold \
confirms the bug, names a wrong root cause, or gives a fixed version that conflicts with \
the gold's). Unstated-but-plausible detail and general security advice are NEVER \
hallucinations. Quote the contradicting response phrase for each.

CONDITION: the response was produced under "{condition}". Under no_context do NOT penalize \
omission of project-internal identifiers (PR numbers, commit SHAs, exact releases); judge \
whether the substance the criterion asks for is conveyed.

Output ONLY a JSON object (criteria in the same order/indices given, none added or dropped):
{{
  "criteria": [{{"index": 1, "verdict": "met"|"partial"|"not_met", "evidence": "...", "reason": "..."}}],
  "hallucinations": [{{"assertion": "...", "evidence": "<quoted response phrase>"}}]
}}
"""

JUDGE_USER_TMPL = """\
QUESTION:
{question}

GOLD ANSWER (maintainer's stated resolution, distilled from the thread):
{gold}

ACCEPTABLE ALTERNATIVES: {alts}

RUBRIC CRITERIA (grade each separately, by index):
{criteria}

RESPONSE (anonymous model, condition={condition}):
{response}
"""


def _format_criteria(rubric: list[dict]) -> str:
    lines = []
    for i, c in enumerate(rubric, 1):
        lines.append(f"{i}. [{c.get('axis', 'correctness')}] {c.get('text', '')}")
    return "\n".join(lines)


def _alts_text(pair: dict) -> str:
    alts = pair.get("acceptable_alternatives") or []
    if isinstance(alts, str):
        alts = [alts]
    return " ".join(a for a in alts if a) or "(none)"


def judge_rubric(judge_model: str, pair: dict, response: str, condition: str) -> dict:
    """Ask the judge to verdict every rubric criterion; return raw judge output."""
    rubric = pair.get("rubric") or []
    system = JUDGE_PROMPT.format(condition=condition)
    user = JUDGE_USER_TMPL.format(
        question=pair.get("question", ""), gold=pair.get("answer", ""),
        alts=_alts_text(pair), criteria=_format_criteria(rubric),
        condition=condition, response=response)
    out = chat_json(judge_model, system, user)
    by_index = {}
    for c in out.get("criteria") or []:
        try:
            by_index[int(c.get("index"))] = c
        except (TypeError, ValueError):
            continue
    return {"by_index": by_index, "hallucinations": out.get("hallucinations") or []}


def score_rubric(rubric: list[dict], judged: dict, condition: str) -> dict:
    """Align judge verdicts to the frozen rubric, apply temporal gating, aggregate."""
    by_index = judged["by_index"]
    grades = []
    for i, crit in enumerate(rubric, 1):
        gradeable = line_gradeable(crit, condition)
        jc = by_index.get(i) or {}
        verdict = jc.get("verdict")
        if verdict not in VERDICT_SCORE:
            verdict = "not_met"
        if not gradeable:
            grades.append({
                "index": i, "text": crit.get("text"), "axis": crit.get("axis"),
                "knowable_at_report": crit.get("knowable_at_report", True),
                "gradeable": False, "verdict": "not_gradeable", "score": None,
                "evidence": "", "reason": "future fact — not gradeable under this condition",
            })
            continue
        grades.append({
            "index": i, "text": crit.get("text"), "axis": crit.get("axis"),
            "knowable_at_report": crit.get("knowable_at_report", True),
            "gradeable": True, "verdict": verdict, "score": VERDICT_SCORE[verdict],
            "evidence": jc.get("evidence") or "", "reason": jc.get("reason") or "",
        })

    def axis_mean(axis):
        xs = [g["score"] for g in grades if g["gradeable"] and g["axis"] == axis]
        return (round(sum(xs) / len(xs), 4) if xs else None), len(xs)

    correctness, n_c = axis_mean("correctness")
    completeness, n_p = axis_mean("completeness")
    all_scores = [g["score"] for g in grades if g["gradeable"]]
    item = round(sum(all_scores) / len(all_scores), 4) if all_scores else None

    base = correctness if n_c else completeness
    if base is None:
        outcome = "ungraded"
    elif base >= TAU_HI:
        outcome = "correct"
    elif base >= TAU_LO:
        outcome = "partial"
    else:
        outcome = "incorrect"

    return {
        "rubric_grades": grades,
        "scores": {
            "correctness": correctness, "completeness": completeness, "item": item,
            "n_correctness": n_c, "n_completeness": n_p, "n_gradeable": len(all_scores),
            "n_total": len(rubric),
        },
        "outcome": outcome,
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def build_gold_index(pairs_path: Path) -> dict[str, tuple[dict, dict]]:
    index = {}
    for thread in load_jsonl(pairs_path):
        for p in thread.get("qa_pairs") or []:
            index[p["qid"]] = (thread, p)
    return index


def cross_check_flags(hard_results: list[dict], outcome: str) -> list[str]:
    """Auxiliary deterministic-vs-rubric consistency flags for human spot-check."""
    flags = []
    gradeable = [r for r in hard_results if r["status"] != "not_gradeable"]
    if gradeable and outcome == "correct" and all(r["status"] == "missing" for r in gradeable):
        flags.append("correct_but_no_hard_fact_matched")
    if gradeable and outcome == "incorrect" and any(r["status"] == "matched" for r in gradeable):
        flags.append("incorrect_but_hard_fact_matched")
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

    print(f"Judge: {judge_model} | rubric source: {pairs_path.name} | "
          f"answers: {len(answers)} from {answers_path}")
    n_err = n_skip = 0
    with open(output_path, "w" if force else "a", encoding="utf-8") as fh:
        for i, ans in enumerate(answers):
            qid = ans["qid"]
            if qid in done:
                continue
            if qid not in gold:
                n_skip += 1
                continue   # no frozen rubric for this item — not part of the release
            thread, pair = gold[qid]
            condition = ans.get("condition", "no_context")
            print(f"[{i+1}/{len(answers)}] {qid} ...", end=" ", flush=True)
            rec = {"qid": qid, "thread_id": ans.get("thread_id"), "repo": ans.get("repo"),
                   "model": ans.get("model"), "condition": condition,
                   "knowledge_type": pair.get("knowledge_type"), "judge_model": judge_model}
            try:
                judged = judge_rubric(judge_model, pair, ans["response"], condition)
                scored = score_rubric(pair.get("rubric") or [], judged, condition)
                hard = grade_hard_facts(thread.get("hard_facts") or {}, ans["response"], condition)
                rec.update(scored)
                rec["hallucinations"] = judged["hallucinations"]
                rec["hallucinated"] = bool(judged["hallucinations"])
                rec["hard_facts"] = hard
                rec["flags"] = cross_check_flags(hard, scored["outcome"])
                sc = scored["scores"]
                print(f"{scored['outcome']} "
                      f"(corr={sc['correctness']} n={sc['n_correctness']}, "
                      f"compl={sc['completeness']} n={sc['n_completeness']})"
                      f"{' HALLUC' if rec['hallucinated'] else ''}"
                      f"{' ' + ','.join(rec['flags']) if rec['flags'] else ''}")
            except Exception as exc:
                rec["error"] = str(exc)
                n_err += 1
                print(f"ERROR: {exc}")
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            if i < len(answers) - 1:
                time.sleep(0.3)

    graded = [r for r in load_jsonl(output_path) if not r.get("error")]
    print(f"\nGraded: {len(graded)} total ({n_err} errors, {n_skip} skipped — no rubric) "
          f"→ {output_path}")

    by = Counter((r["knowledge_type"], r["outcome"]) for r in graded)
    print("\nOutcome by knowledge type:")
    for (kt, oc), n in sorted(by.items(), key=lambda x: (str(x[0][0]), str(x[0][1]))):
        print(f"  {str(kt):11s} {str(oc):10s} {n}")

    def mean_of(key):
        xs = [r["scores"][key] for r in graded
              if r.get("scores") and r["scores"].get(key) is not None]
        return round(sum(xs) / len(xs), 3) if xs else None

    print(f"\nMean correctness score:  {mean_of('correctness')}")
    print(f"Mean completeness score: {mean_of('completeness')}")
    n_h = sum(1 for r in graded if r.get("hallucinated"))
    print(f"Hallucination rate: {n_h}/{len(graded)}")
    flagged = sum(1 for r in graded if r.get("flags"))
    if flagged:
        print(f"Cross-check flags for human review: {flagged} records")


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage 3: rubric grading (single judge).")
    ap.add_argument("--answers", type=Path, required=True,
                    help="answers_*.jsonl produced by the harness (answer/agent/external)")
    ap.add_argument("--pairs", type=Path, default=DEFAULT_PAIRS,
                    help="rubric-bearing benchmark jsonl (default: security_benchmark_release.jsonl)")
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
