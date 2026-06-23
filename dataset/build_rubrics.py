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
  each rubric criterion = {text, axis(correctness|completeness), source_quote, source_loc}
  every criterion MUST quote a verbatim evidence span; criteria without grounded spans are dropped.
  axis is a kind, not a weight: correctness gates the outcome, completeness adds coverage
  (no numeric weights — grading rolls criteria up by axis, never by a weighting constant).

Validation gate (Stage 2, no LLM):
  - source_quote must string-match the assembled evidence  → else REJECT the criterion
  - axis ∈ {correctness, completeness}, 1..5 criteria (capped)
  - knowable_at_report recomputed deterministically from source_loc × resolution_case
  - items with <2 surviving criteria flagged low_resolution

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
THREAD_CHAR_CAP = 80_000
# total fix-diff chars beyond which the diff is NOT dumped into the rubric
# corpus; flagged for human review instead
OVERSIZED_DIFF_CHARS = 20_000
# hard cap per question — too many criteria saturate (every system clears them;
# discrimination collapses). Set 3 for tighter.
MAX_RUBRIC_CRITERIA = 5

# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = """You are an expert security engineer building a GRADING RUBRIC for one developer security query.

A rubric is a short checklist of claims a GOOD ANSWER should make. Each criterion is graded later as met/partial/not-met by a judge.
Your job is ONLY to author the criteria that capture the information content the ANSWER contributes.

WHAT COUNTS AS THE ANSWER (the only thing a rubric criterion may assert):
- the GOLD ANSWER text and the answerer's reply, AND
- the substance of whatever that answer references — the FIX DIFF, the advisory, the fixed version, the hard facts.
The fix diff/advisory ARE the answer when the reply is a bare pointer ("see PR #N", "patch: <url>"): the answer is telling the reader "the resolution is there", so its content is that resolution.

WHAT IS CONTEXT, NOT A SOURCE:
- the QUESTION and any other thread comments are CONTEXT so you can interpret the answer. The candidate being graded ALREADY RECEIVES THE QUESTION. NEVER author a rubric criterion whose content comes from the question or from a non-answer commenter — that would credit the candidate for repeating its own input. If the reporter already diagnosed the root cause in the question and the answer merely confirms it, the gradeable contribution is the CONFIRMATION/VERDICT, not the diagnosis.

HARD RULES:
- Every criterion MUST be supported by a span you copy from the ANSWER-SIDE evidence (gold answer / answerer reply / fix diff / advisory / hard facts) into "source_quote". Copy it as closely as you can. If you cannot point to answer-side evidence for a claim, DO NOT write the criterion. Never invent versions, CVEs, files, or behavior not present in the evidence.
- The rubric "text" is a PARAPHRASED, checkable claim (a criterion), NOT a verbatim sentence. "source_quote" is the verbatim-as-possible provenance span; "text" is the normalized claim a judge checks.
- Two axes only (a KIND, not a weight — correctness gates the outcome, completeness adds coverage; do NOT emit numeric weights):
    "correctness" = a load-bearing fact/verdict that must be RIGHT (the real-vs-by-design call, the fixed version, whether the user is affected, the root-cause location AS ESTABLISHED BY THE ANSWER/FIX). A missed correctness criterion fails the item regardless of coverage.
    "completeness" = supporting coverage a thorough answer gives (the mechanism, a caveat/scope, an alternative valid fix).
- 1 to 5 criteria. A terse answer gets few criteria — that is correct. DO NOT pad to reach a count. Prefer fewer, load-bearing criteria: too many criteria saturate the rubric.
- Grade soundness, not diff-identity: a remediation criterion should describe WHAT any correct fix must achieve, so any valid approach can satisfy it.
- REFERENCE-ONLY ANSWERS (answer is essentially a pointer). Handle by what it points to:
    (A/B) CODE-FIX pointer with a FIX DIFF present → DERIVE the correctness (root cause) and completeness (remediation) criteria FROM THE FIX DIFF — that diff is the answer's real substance.
    (C) VERSION / ADVISORY pointer ("fixed in 2.32.4", "see GHSA-..."): name the fixed VERSION as a CORRECTNESS criterion (it is the load-bearing fact for "which version fixes this"), sourced from HARD FACTS; the advisory becomes a COMPLETENESS pointer criterion. No diff needed.
    (D) EXPLANATION-WITH-LINK ("this depends on the runtime, see <docs>", "keep a blacklist of tokens"): the answer's OWN PROSE is the substance — author criteria from the reply text. NEVER invent the linked document's contents; you cannot see them.
  In every reference-only case the reference itself becomes EXACTLY ONE completeness pointer criterion ("points to the fix: <commit/PR/version/advisory>"); leave its grading to the temporal gate (it may be a future fact). Do NOT score the answer as empty just because its prose is thin. If there is no diff, no version, and only a bare link, it is fine to emit only that one pointer criterion.
- "acceptable_alternatives": note valid non-maintainer answers that should still count.
- "ceiling_note": which criteria the answerer's own reply already satisfies."""

TEMPLATE = """================ CONTEXT (to interpret the answer — DO NOT author rubric criteria from this section) ================
QUERY (self-contained — the candidate already receives this; never credit a criterion for repeating it):
{question}

FULL THREAD (background only):
{thread}

================ ANSWER SIDE (the ONLY source for rubric criteria) ================
GOLD ANSWER (answerer role: {answerer_role}):
{answer}

ANSWERER'S RAW REPLY:
{answer_comment}

REPO: {repo}    ISSUE TITLE: {title}
RESOLUTION CASE: {resolution_case}   (fix_before = fix predates the report; fix_after = fix landed after; explanation_only = no code fix)
{grading_policy}
HARD FACTS: {hard_facts}
ADVISORY URLS: {advisory_urls}

FIX DIFFS (the code the answer references — its real substance):
{diffs}

---
Author the rubric. Return ONLY valid JSON (no markdown fences):
{{
  "rubric": [
    {{"text": "<one checkable claim>", "axis": "correctness",
      "source_quote": "<span copied as-closely-as-possible from the ANSWER SIDE above>",
      "source_loc": "gold_answer | answer_reply | fix_diff:<path> | advisory | hard_facts"}}
  ],
  "acceptable_alternatives": "<note or empty string>",
  "ceiling_note": "<which criteria the maintainer reply satisfies>"
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


def answer_reply(record):
    """The answerer's raw maintainer reply (distinct from the normalized gold answer)."""
    c = comment_by_id(record, record.get("answer_comment_id"))
    return (c.get("body") or "").strip() if c else ""


def diff_total_chars(record):
    return sum(len(f.get("patch") or "")
               for a in (record.get("fix_artifacts") or [])
               for f in (a.get("files") or []))


def is_oversized_diff(record):
    return diff_total_chars(record) > OVERSIZED_DIFF_CHARS


def format_diffs(record):
    out = []
    rc = record.get("resolution_case")
    oversized = is_oversized_diff(record)
    # fix_before: the fix already landed and is retrievable at report time, so the graded
    # task mirrors the maintainer — IDENTIFY/cite the existing PR/commit/version, NOT
    # reproduce the patch. Withhold the diff bytes so no diff-reproduction criterion is authored.
    pointer_only = rc == "fix_before"
    for a in record.get("fix_artifacts") or []:
        nfiles = len(a.get("files") or [])
        head = f"### {a.get('type')} {a.get('id')}  ({a.get('url')})  fix_time={a.get('fix_time')}"
        if pointer_only:
            out.append(f"{head}\n--- fix already landed before the report; "
                       f"grade identification of this resolution, not diff reproduction "
                       f"({nfiles} files) ---")
            continue
        if oversized:
            # Don't dump a huge diff into the corpus/prompt — keep only the pointer.
            out.append(f"{head}\n--- diff too large, needs human review "
                       f"({nfiles} files, {diff_total_chars(record)} chars; omitted) ---")
            continue
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
    """ANSWER-SIDE corpus the validation gate matches source_quote against.

    Deliberately EXCLUDES the question and non-answer thread comments: a rubric criterion
    grounded only in the question (which the candidate already receives) must fail the
    gate. Answer side = gold answer + answerer reply + referenced fix diff + advisory +
    hard facts.
    """
    pieces = [
        qa.get("answer") or "",
        answer_reply(record),
        format_diffs(record),
        format_hard_facts(record.get("hard_facts") or {}),
        " ".join((record.get("hard_facts") or {}).get("advisory_urls") or []),
    ]
    return "\n".join(pieces)


_CITE_FIX = re.compile(r"github\.com/[\w.-]+/[\w.-]+/(?:commit|pull)/|\bPR\b\s*#?\d+|#\d{2,}", re.I)
_CITE_VER = re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b|GHSA-[\w-]+|CVE-\d{4}-\d+|advisor", re.I)
_HAS_URL = re.compile(r"https?://\S+")


def _has_usable_diff(record):
    for a in record.get("fix_artifacts") or []:
        if any((f.get("patch") or "").strip() for f in a.get("files") or []):
            return True
    return False


def classify_reference(record, qa):
    """Hint for the drafter + human verifier — which reference-only sub-type this is.

    A/B code-fix pointer (diff present) · C version/advisory pointer · D explanation+link ·
    E citable but unrecoverable · none = substantive answer (not reference-only)."""
    ans = (qa.get("answer") or "").strip()
    hf = record.get("hard_facts") or {}
    is_pointerish = len(ans.split()) <= 30 and bool(_HAS_URL.search(ans) or _CITE_FIX.search(ans)
                                                    or _CITE_VER.search(ans))
    if not is_pointerish:
        return "none"
    if _has_usable_diff(record):
        return "code_fix"          # A/B
    if hf.get("fixed_versions") or hf.get("advisory_urls") or _CITE_VER.search(ans):
        return "version_advisory"  # C
    if _HAS_URL.search(ans) or len(ans.split()) > 12:
        return "explanation_link"  # D
    return "unrecoverable"          # E


# --------------------------------------------------------------------------- #
def _norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


_STOP = frozenset(
    "the a an of to in on at for and or but is are was were be been being this that these those "
    "it its as by with from into when where which who whom whose if then than so not no nor can "
    "could should would may might will shall do does did has have had ha he she they we you i".split()
)


def _content_tokens(s):
    return [t for t in re.findall(r"[a-z0-9_./#-]+", _norm(s)) if t not in _STOP and len(t) > 1]


def span_supported(quote, corpus_norm, corpus_tokens):
    """Grounding check, tolerant of paraphrase. The point is 'this claim is backed by
    answer-side evidence', not 'the model copied chars exactly'. Exact substring wins;
    otherwise require most CONTENT tokens of the quote to appear in the answer-side corpus
    (catches reordered/paraphrased spans; rejects fabricated ids/versions/files not present
    and rejects spans lifted from the question, which is not in the corpus)."""
    q = _norm(quote)
    if len(q) < 8:
        return False
    if q in corpus_norm:
        return True
    if len(q) > 120 and q[:80] in corpus_norm:
        return True
    toks = _content_tokens(quote)
    if len(toks) < 4:
        return False
    hits = sum(1 for t in toks if t in corpus_tokens)
    return hits / len(toks) >= 0.8


def validate(draft, corpus, resolution_case):
    """Drop ungrounded/malformed criteria; recompute knowable_at_report. Returns (criteria, info)."""
    corpus_norm = _norm(corpus)
    corpus_tokens = set(_content_tokens(corpus))
    kept, rejected = [], []
    for crit in (draft.get("rubric") or []):
        reason = None
        axis = crit.get("axis")
        if axis not in ("correctness", "completeness"):
            reason = f"bad axis {axis!r}"
        elif not (crit.get("text") or "").strip():
            reason = "empty text"
        elif not span_supported(crit.get("source_quote"), corpus_norm, corpus_tokens):
            reason = "source_quote not grounded in answer-side evidence"
        if reason:
            rejected.append({"text": crit.get("text"), "reason": reason,
                             "source_quote": crit.get("source_quote")})
            continue
        # deterministic temporal gate: a criterion that REFERENCES the fix is a future fact
        # under fix_after — the diff criteria, the one pointer criterion, and hard_facts/advisory
        # version & fix-PR/commit criteria. fix_before / explanation_only keep the drafter's
        # value (default True) for the human to confirm.
        loc = (crit.get("source_loc") or "").lower()
        text = (crit.get("text") or "").lower()
        references_fix = (
            loc.startswith("fix_diff")
            or loc in ("hard_facts", "advisory")
            or "point to the fix" in text or "points to" in text or "identifies the fix" in text
        )
        if references_fix and resolution_case == "fix_after":
            crit["knowable_at_report"] = False
        else:
            crit.setdefault("knowable_at_report", True)
        kept.append(crit)
    info = {
        "n_kept": len(kept),
        "n_rejected": len(rejected),
        "rejected": rejected,
        "low_resolution": len(kept) < 2,
    }
    return kept, info


def cap_rubric(criteria, limit):
    """Enforce the per-question criterion cap deterministically. Keep correctness
    (outcome-gating) criteria first in their drafted order, then completeness, truncate to
    `limit`. Returns (kept, n_dropped)."""
    if len(criteria) <= limit:
        return criteria, 0
    ordered = [c for c in criteria if c.get("axis") == "correctness"] + \
              [c for c in criteria if c.get("axis") != "correctness"]
    return ordered[:limit], len(criteria) - limit


def grading_policy(resolution_case):
    """Per-case authoring policy injected into the prompt — keyed on the fix's temporal
    relation to the report. fix_before = retrieval task; fix_after = remediation-reasoning."""
    if resolution_case == "fix_before":
        return ("GRADING POLICY (fix_before): the fix ALREADY LANDED before this query and is "
                "retrievable from the repo at report time. Mirror the maintainer: the gradeable "
                "contribution is IDENTIFYING the existing resolution. Author ONE correctness "
                "pointer criterion — 'identifies the existing fix: <PR/commit/fixed version>' "
                "sourced from HARD FACTS — plus, if the reply explains it, at most one completeness "
                "criterion on the root cause/verdict. Do NOT author criteria that require "
                "reproducing the patch; "
                "the diff is withheld on purpose. Put equivalent valid forms (correct fixed version, "
                "correct description of the landed change) in acceptable_alternatives.")
    if resolution_case == "fix_after":
        return ("GRADING POLICY (fix_after): the fix landed AFTER this query — it is NOT retrievable "
                "at report time. Grade whether a proposed remediation goes in the SAME DIRECTION as "
                "the eventual fix. Author SEMANTIC criteria describing WHAT any correct fix must achieve "
                "(derived from the diff), never the literal patch; any valid approach should satisfy them.")
    return ("GRADING POLICY: no code fix is cited — author criteria from the answer's own prose / "
            "advisory / hard facts only.")


def oversized_review_criterion(record):
    """Deterministic rubric criterion for records whose fix diff was too large to auto-ground.

    Injected post-validation (bypasses the grounding gate by design): the diff was
    withheld from the corpus, so no LLM criterion can cite it. A human reviewer extracts the
    graded change. knowable_at_report follows the same temporal rule as a fix-referencing
    criterion: a future fact under fix_after."""
    urls = [a.get("url") for a in (record.get("fix_artifacts") or []) if a.get("url")]
    return {
        "axis": "correctness",
        "text": "diff too large, needs human review",
        "source_quote": "; ".join(urls) or "(fix artifact, diff omitted)",
        "source_loc": "fix_diff_oversized",
        "knowable_at_report": record.get("resolution_case") != "fix_after",
        "needs_human_review": True,
    }


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
        answerer_role=record.get("answerer_role", "unknown"),
        answer_comment=answer_reply(record) or "(no separate maintainer reply comment)",
        resolution_case=record.get("resolution_case", "(not yet extracted — run extract_fixes.py)"),
        grading_policy=grading_policy(record.get("resolution_case")),
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
              "Run dataset/extract_fixes.py first for diff-grounded criteria + temporal gating.")

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
                criteria, info = validate(draft, corpus, record.get("resolution_case"))
                # oversized→human-review only applies where the diff is actually used as
                # rubric substance: fix_after. fix_before withholds the diff by design.
                oversized = is_oversized_diff(record) and \
                    record.get("resolution_case") == "fix_after"
                # enforce the per-question cap; reserve one slot for an injected review criterion
                limit = MAX_RUBRIC_CRITERIA - 1 if oversized else MAX_RUBRIC_CRITERIA
                criteria, n_capped = cap_rubric(criteria, limit)
                info["n_capped"] = n_capped
                if oversized:
                    criteria.append(oversized_review_criterion(record))
                    info["oversized_diff"] = True
                info["n_kept"] = len(criteria)
                info["low_resolution"] = len(criteria) < 2
                out = {
                    "id": record["id"],
                    "qid": qid,
                    "repo": record.get("repo"),
                    "question": qa.get("question"),
                    "knowledge_type": qa.get("knowledge_type"),
                    "resolution_case": record.get("resolution_case"),
                    "reference_type": classify_reference(record, qa),
                    "oversized_diff": oversized,
                    "rubric": criteria,
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
                flag = ("  OVERSIZED_DIFF" if oversized else "") + \
                       ("  LOW_RES" if info["low_resolution"] else "")
                print(f"[{n_pairs}] {qid:40s} ref={out['reference_type']:16s} "
                      f"criteria={info['n_kept']} rejected={info['n_rejected']}{flag}")

    print(f"\ndrafted {n_pairs} rubrics → {out_path}")
    print(f"low_resolution (<2 criteria): {n_low}    total criteria rejected by gate: {n_rej}")
    print("NEXT: human-verify all rubrics (two authors) in the review UI, then freeze "
          "to dataset/rubrics_final.jsonl.")


if __name__ == "__main__":
    main()
