"""
build_rubrics.py — Stage 0-2 of the SecDevQA grading pipeline (grading_scheme_final.md).

For every qa_pair (qid) in security_benchmark_final.jsonl, draft a per-item, span-traceable
grading rubric, then run a mechanical validation gate. Output is a DRAFT to be human-verified
(two authors) and frozen before any grading uses it.

Evidence given to the drafter (Stage 0):
  - issue title + normalized question + gold answer
  - full comment thread
  - fix_artifacts diffs   (run dataset/extract_fixes.py FIRST so this field exists)
  - hard_facts + advisory URLs + resolution_case

Drafting (Stage 1, LiteLLM, any provider — mirrors open_coding/open_code.py):
  each rubric line = {text, axis(correctness|completeness), weight(1|2), source_quote, source_loc}
  every line MUST quote a verbatim evidence span; lines without grounded spans are dropped.

Validation gate (Stage 2, no LLM):
  - source_quote must string-match the assembled evidence  → else REJECT the line
  - axis ∈ {correctness, completeness}, weight ∈ {1,2}, 1..8 lines
  - knowable_at_report recomputed deterministically from source_loc × resolution_case
  - items with <2 surviving lines flagged low_resolution

Output: dataset/rubrics_draft.jsonl (resumable by qid) + a printed validation summary.

Usage:
  /local/home/amamun/envs/devqa/bin/python dataset/build_rubrics.py --model openai/gpt-5.4-mini
  /local/home/amamun/envs/devqa/bin/python dataset/build_rubrics.py --model anthropic/claude-sonnet-4-6 --limit 5
  /local/home/amamun/envs/devqa/bin/python dataset/build_rubrics.py --model openai/gpt-5.4-mini --force
"""

import argparse
import json
import re
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent
INPUT_FILE = ROOT / "dataset" / "security_benchmark_final.jsonl"
OUTPUT_FILE = ROOT / "dataset" / "rubrics_draft.jsonl"

PATCH_CHAR_CAP = 12_000   # per-artifact diff budget inside the prompt
THREAD_CHAR_CAP = 40_000

# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = """You are an expert security engineer building a GRADING RUBRIC for one developer security query.

A rubric is a short checklist of claims a good answer should make. Each line is graded later as met/partial/not-met by a judge. 
Your job is ONLY to author the lines from the supplied evidence.

HARD RULES:
- Every line MUST be supported by a verbatim span you copy from the evidence into "source_quote". If you cannot quote evidence for a claim, DO NOT write the line. Never invent versions, CVEs, files, or behavior not present in the evidence.
- Use the WHOLE evidence (thread + fix diff + advisory + hard facts), not just the maintainer's reply. The maintainer reply is often terse; the fix diff usually carries the real substance.
- Two axes only:
    "correctness" = a load-bearing fact/verdict that must be RIGHT (the real-vs-by-design call, the fixed version, whether the user is affected, the root-cause location). weight 2.
    "completeness" = supporting coverage a thorough answer gives (the mechanism, a caveat/scope, an alternative valid fix). weight 1.
- 1 to 8 lines. A terse item gets few lines — that is correct. DO NOT pad.
- Grade soundness, not diff-identity: a remediation line should describe WHAT any correct fix must achieve, so any valid approach can satisfy it.
- REFERENCE-ONLY ANSWERS: if the gold answer is essentially a bare link ("Patch commit: <url>", "see PR #N") with no explanation, DERIVE the correctness (root cause) and completeness (remediation) lines FROM THE FIX DIFF below — that diff is the real substance. The reference itself becomes ONE completeness line ("points to the fix: <commit/PR/release>"); leave its grading to the temporal gate (it may be a future fact). Do NOT score the answer as empty just because its prose is thin.
- "acceptable_alternatives": note valid non-maintainer answers that should still count.
- "ceiling_note": which lines the maintainer's own reply already satisfies."""

TEMPLATE = """QUERY (self-contained):
{question}

GOLD ANSWER (maintainer/thread, role: {answerer_role}):
{answer}

REPO: {repo}    ISSUE TITLE: {title}
RESOLUTION CASE: {resolution_case}   (fix_before = fix predates the report; fix_after = fix landed after; explanation_only = no code fix)
HARD FACTS: {hard_facts}
ADVISORY URLS: {advisory_urls}

FULL THREAD:
{thread}

FIX DIFFS (proposed code from the answerer's commit/PR):
{diffs}

---
Author the rubric. Return ONLY valid JSON (no markdown fences):
{{
  "rubric": [
    {{"text": "<one checkable claim>", "axis": "correctness", "weight": 2,
      "source_quote": "<verbatim span copied from the evidence above>",
      "source_loc": "comment | gold_answer | fix_diff:<path> | advisory | hard_facts"}}
  ],
  "acceptable_alternatives": "<note or empty string>",
  "ceiling_note": "<which lines the maintainer reply satisfies>"
}}"""


# --------------------------------------------------------------------------- #
def comment_by_id(record, cid):
    for c in record.get("comments") or []:
        if c.get("id") == cid:
            return c
    return None


def format_thread(record):
    q_id = record.get("question_comment_id")
    a_id = record.get("answer_comment_id")
    parts = []
    for c in record.get("comments") or []:
        tag = " [QUESTION]" if c.get("id") == q_id else (" [ANSWER]" if c.get("id") == a_id else "")
        parts.append(f"[{c.get('author', '?')}{tag}]:\n{(c.get('body') or '').strip()}")
    return "\n\n".join(parts)[:THREAD_CHAR_CAP]


def format_diffs(record):
    out = []
    for a in record.get("fix_artifacts") or []:
        head = f"### {a.get('type')} {a.get('id')}  ({a.get('url')})  fix_time={a.get('fix_time')}"
        files = []
        budget = PATCH_CHAR_CAP
        for f in a.get("files") or []:
            patch = f.get("patch") or ""
            if budget <= 0:
                files.append(f"--- {f.get('path')} (omitted, budget) ---")
                continue
            patch = patch[:budget]
            budget -= len(patch)
            files.append(f"--- {f.get('path')} ---\n{patch}")
        out.append(head + "\n" + "\n".join(files))
    return "\n\n".join(out) if out else "(no fix commit/PR cited)"


def format_hard_facts(hf):
    parts = []
    for k, label in [("cve_ids", "CVEs"), ("ghsa_ids", "GHSAs"), ("cwe_ids", "CWEs"),
                     ("fixed_versions", "fixed in"), ("fix_prs", "fix PRs"),
                     ("fix_commits", "fix commits")]:
        if hf.get(k):
            parts.append(f"{label}: {', '.join(hf[k])}")
    return "; ".join(parts) or "none"


def assemble_evidence(record, qa):
    """The exact corpus the validation gate matches source_quote against."""
    pieces = [
        qa.get("question") or "",
        qa.get("answer") or "",
        record.get("title") or "",
        format_thread(record),
        format_diffs(record),
        format_hard_facts(record.get("hard_facts") or {}),
        " ".join((record.get("hard_facts") or {}).get("advisory_urls") or []),
    ]
    return "\n".join(pieces)


# --------------------------------------------------------------------------- #
def _norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def span_supported(quote, corpus_norm):
    q = _norm(quote)
    if len(q) < 8:
        return False
    if q in corpus_norm:
        return True
    # lenient tail: models sometimes paraphrase the end of a long quote
    if len(q) > 120 and q[:80] in corpus_norm:
        return True
    return False


def validate(draft, corpus, resolution_case):
    """Drop ungrounded/malformed lines; recompute knowable_at_report. Returns (lines, info)."""
    corpus_norm = _norm(corpus)
    kept, rejected = [], []
    for ln in (draft.get("rubric") or []):
        reason = None
        axis = ln.get("axis")
        weight = ln.get("weight")
        if axis not in ("correctness", "completeness"):
            reason = f"bad axis {axis!r}"
        elif weight not in (1, 2):
            reason = f"bad weight {weight!r}"
        elif not (ln.get("text") or "").strip():
            reason = "empty text"
        elif not span_supported(ln.get("source_quote"), corpus_norm):
            reason = "source_quote not found in evidence"
        if reason:
            rejected.append({"text": ln.get("text"), "reason": reason,
                             "source_quote": ln.get("source_quote")})
            continue
        # deterministic temporal gate: a diff-sourced line is a future fact under fix_after.
        # Version/advisory lines keep the drafter's value (default True) for the human to confirm.
        loc = (ln.get("source_loc") or "").lower()
        diff_sourced = loc.startswith("fix_diff")
        if diff_sourced and resolution_case == "fix_after":
            ln["knowable_at_report"] = False
        else:
            ln.setdefault("knowable_at_report", True)
        kept.append(ln)
    info = {
        "n_kept": len(kept),
        "n_rejected": len(rejected),
        "rejected": rejected,
        "low_resolution": len(kept) < 2,
    }
    return kept, info


# --------------------------------------------------------------------------- #
def call_litellm(prompt, model, api_base=None):
    import litellm
    kwargs = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": prompt}],
        "max_tokens": 8192,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    if api_base:
        kwargs["api_base"] = api_base
    for attempt in range(3):
        try:
            text = litellm.completion(**kwargs).choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"  [litellm] JSON parse failed attempt {attempt + 1}: {e}")
        except Exception as e:
            print(f"  [litellm] attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
    return None


def build_prompt(record, qa):
    hf = record.get("hard_facts") or {}
    return TEMPLATE.format(
        question=(qa.get("question") or "")[:8192],
        answer=(qa.get("answer") or "")[:8192],
        repo=record.get("repo", ""),
        title=record.get("title", ""),
        resolution_case=record.get("resolution_case", "(not yet extracted — run extract_fixes.py)"),
        hard_facts=format_hard_facts(hf),
        advisory_urls=", ".join(hf.get("advisory_urls") or []) or "none",
        thread=format_thread(record),
        diffs=format_diffs(record),
    )


def load_done(path, force):
    if force or not path.exists():
        return set()
    done = set()
    with open(path) as f:
        for line in f:
            try:
                done.add(json.loads(line)["qid"])
            except Exception:
                pass
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="LiteLLM model string")
    ap.add_argument("--input", default=str(INPUT_FILE))
    ap.add_argument("--output", default=str(OUTPUT_FILE))
    ap.add_argument("--api-base", default=None)
    ap.add_argument("--limit", type=int, default=None, help="limit number of THREADS processed")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out_path = Path(args.output)
    records = [json.loads(l) for l in open(args.input) if l.strip()]
    if args.limit:
        records = records[: args.limit]
    done = load_done(out_path, args.force)
    if args.force and out_path.exists():
        out_path.unlink()

    if any("fix_artifacts" not in r for r in records):
        print("WARNING: some records lack 'fix_artifacts'/'resolution_case'. "
              "Run dataset/extract_fixes.py first for diff-grounded lines + temporal gating.")

    n_pairs = n_low = n_rej = 0
    with open(out_path, "a") as fout:
        for record in records:
            for qa in record.get("qa_pairs") or []:
                qid = qa.get("qid")
                if qid in done:
                    continue
                draft = call_litellm(build_prompt(record, qa), args.model, args.api_base)
                if draft is None:
                    print(f"  SKIP {qid}: drafter returned nothing")
                    continue
                corpus = assemble_evidence(record, qa)
                lines, info = validate(draft, corpus, record.get("resolution_case"))
                out = {
                    "id": record["id"],
                    "qid": qid,
                    "repo": record.get("repo"),
                    "question": qa.get("question"),
                    "knowledge_type": qa.get("knowledge_type"),
                    "resolution_case": record.get("resolution_case"),
                    "rubric": lines,
                    "acceptable_alternatives": draft.get("acceptable_alternatives", ""),
                    "ceiling_note": draft.get("ceiling_note", ""),
                    "model": args.model,
                    "_validation": info,
                    "status": "draft",      # → human verification sets accepted/edited
                }
                fout.write(json.dumps(out) + "\n")
                fout.flush()
                n_pairs += 1
                n_low += int(info["low_resolution"])
                n_rej += info["n_rejected"]
                flag = "  LOW_RES" if info["low_resolution"] else ""
                print(f"[{n_pairs}] {qid:40s} lines={info['n_kept']} "
                      f"rejected={info['n_rejected']}{flag}")

    print(f"\ndrafted {n_pairs} rubrics → {out_path}")
    print(f"low_resolution (<2 lines): {n_low}    total lines rejected by gate: {n_rej}")
    print("NEXT: human-verify all rubrics (two authors) in the review UI, then freeze "
          "to dataset/rubrics_final.jsonl.")


if __name__ == "__main__":
    main()
