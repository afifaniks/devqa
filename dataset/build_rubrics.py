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
# --- shared base: identical for every item, condition-independent ---------------
SYSTEM_BASE = """You are a security engineer writing a grading rubric for one developer security question.

The rubric is a short checklist of things a good and correct answer should get right. 
Later, a judge takes a candidate answer and marks each item met, partly met, or missed. Your job is to write those items.

Grade only what the answer adds:
- The "answer" is the maintainer's reply plus whatever it leans on — a fix diff, an advisory, a fixed version, or the hard facts listed below.
- If the reply is just a pointer ("fixed in #123", "see this advisory"), then the thing it points to is the answer. Grade that content.
- The question and the rest of the thread are background. The candidate already has the question, so don't write an item that just repeats it. 
If the reporter already explained the bug and the maintainer only agreed, grade the agreement (the verdict), not the explanation.

Grade the conclusion, not the process:
- Skip workflow and status entirely. None of these is ever an item, as correctness OR completeness:
    * that the bug was reproduced, or "reproducible", or that a repro example/sandbox was provided;
    * that a patch is coming / being prepared / merged / will be released / which branch it lands in;
    * the release date, or that no release date is known;
    * that a workaround is "temporary" or "until the next release", or that a fix is "permanent" — grade the workaround's technical content, never its temporary/permanent status;
    * that the maintainer will coordinate with, contact, or notify anyone (GitHub Security, Snyk, a DB).
  These describe how the work happened, not the security answer.
- Don't smuggle that status back in as a TAIL on a good item. Keep each item to its technical claim and stop — do not append "...and confirms it was reproduced", "...and a patch was merged", or "...but doesn't know when it ships". State the security fact; drop the workflow clause.
- By default, do NOT write a "this is a real bug" item. Most reports here come with the reporter's own analysis (a crash, a source-level NULL-deref, an overflow they found), and a maintainer agreeing is the expected, low-information outcome. Saying "yes, it's real" to such a report is not a graded skill — grade the technical substance instead (root cause, what a fix must do).
- Add a verdict item ONLY as an exception: when the call was genuinely in doubt and a competent responder could reasonably have gone the other way — by-design, not-affected, intended behavior, disputed severity, won't-fix, a false positive in a scanner/DB, or "this isn't actually exploitable." Then write it as the verdict ("correctly judges this is a real <type> bug, not by-design" / "correctly identifies this as a false positive") — never as "reproduced it". If you can't name a plausible opposite conclusion, there is no verdict item.

Two kinds of items:
- correctness — something that has to be right: the verdict, who is affected, the root cause, what a fix has to do. Getting one of these wrong should sink the answer.
- completeness — extra depth a strong answer adds: the mechanism, a caveat, an alternative fix.
This is just a label, not a score. Don't attach numbers.

Keep items grounded, precise, and few:
- Every item needs a real quote from the answer side (reply, diff, advisory, or hard facts) in "source_quote". If you can't quote it, don't write it. Never invent versions, CVEs, files, or behavior.
- "text" is your plain restatement of the claim; "source_quote" is where it came from.
- One item = one idea that matters. When the answer is a single procedure with several mechanical steps (e.g. "add this manifest flag, create this folder, drop this config file, add these trust anchors"), do NOT make each step its own item — capture the essential security requirement in one item and let the steps live inside its text or in acceptable_alternatives. Splitting one fix into many near-duplicate items wrongly forces a candidate to hit every sub-step.
- Write 1 to 5 items. A short answer gets a short rubric — that's fine. Don't pad. But never return an empty rubric: if the answer says anything substantive, at least one item must capture its core resolution claim.

Also fill in "acceptable_alternatives": other answers that should still count as correct."""

# --- per-condition specialization, appended to SYSTEM_BASE ----------------------
COND_FIX_BEFORE = """This question is a "fix already existed" case.

The fix was already in the repo when the question was asked, so this is really a "can you find it" task — and you are not shown the diff. Reward the answer for pointing to that existing fix.
- Write one correctness item: identifies the existing fix (the PR, commit, or fixed version), taken from the hard facts or the reply.
- The fix must be a DISTINCT resolving artifact — the PR/commit/version that fixed the bug. If the question already names a commit or version the reporter is running (the one they are reporting against), that is NOT the fix; never echo it back as "fixed in <that same commit/version>".
- If the reply also explains the root cause, you may add one completeness item for that.
- Don't ask the answer to reproduce or quote the patch — it isn't available to you.
- Put close-enough answers (the right version, an accurate description of the change) in "acceptable_alternatives"."""

COND_FIX_AFTER = """This question is a "fix came later" case.

The fix landed after the question was asked, so the candidate couldn't have looked it up — it didn't exist yet. You're shown the diff only so you know which direction a correct fix should go. Grade whether the answer heads that way.
- Write items for what any correct fix has to do — e.g. "checks the result of <fn> for NULL before using it", "does the size math in a wider type so it can't overflow". Describe the goal, not the exact patch; any sound approach should pass.
- If the answer takes a side on whether the bug is real, add the verdict item.
- Don't point at the specific fix that eventually landed: no "see PR #123", no "fixed in 7.1.2". The PR, commit, release, and version number all came after the question, so they're off limits — only the direction of the fix is fair game."""

COND_EXPLANATION = """This question has no code fix — it's resolved by an explanation, a fixed version, or an advisory.

Build the rubric from the reply, the advisory, and the hard facts only.
- If it names a fixed version or advisory ("fixed in 2.32.4", "see GHSA-..."): make the version a correctness item (that's the key fact), and the advisory link a completeness item.
- If it's an explanation with a link ("depends on your runtime, see the docs"): grade the reply's own words. You can't see the linked page, so don't guess what's on it.
- A short answer is fine. If all there is is one link, one item is enough — don't mark it empty just for being brief."""

_COND_BLOCKS = {
    "fix_before": COND_FIX_BEFORE,
    "fix_after": COND_FIX_AFTER,
    "explanation_only": COND_EXPLANATION,
}


def system_prompt(resolution_case):
    """Compose the condition-specific system prompt. `undetermined` (fix cited but no
    usable timestamp) is treated as fix_after — the safe default that never credits a
    possibly-future fix identifier."""
    block = _COND_BLOCKS.get(resolution_case, COND_FIX_AFTER)
    return SYSTEM_BASE + "\n\n" + block


TEMPLATE = """# Background (for understanding only — don't write rubric items from this)

The developer's question (the candidate already gets this, so don't reward repeating it):
{question}

The full thread, for context:
{thread}

# The answer (this is what your rubric items come from)

Gold answer (from the {answerer_role}):
{answer}

The maintainer's raw reply:
{answer_comment}

Repo: {repo}   Issue: {title}
Resolution case: {resolution_case}
Hard facts: {hard_facts}
Advisory URLs: {advisory_urls}

The fix diff the answer relies on:
{diffs}

---
Write the rubric for this resolution case, following the case-specific guidance in your instructions.
Reply with JSON only, no markdown fences:
{{
  "rubric": [
    {{"text": "the claim, in plain words", "axis": "correctness",
      "source_quote": "a quote copied from the answer above",
      "source_loc": "gold_answer | answer_reply | fix_diff:<path> | advisory | hard_facts"}}
  ],
  "acceptable_alternatives": "other answers that should still count, or empty"
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
        crit_text = crit.get("text") or ""
        if axis not in ("correctness", "completeness"):
            reason = f"bad axis {axis!r}"
        elif not crit_text.strip():
            reason = "empty text"
        elif not span_supported(crit.get("source_quote"), corpus_norm, corpus_tokens):
            reason = "source_quote not grounded in answer-side evidence"
        if reason:
            rejected.append({"text": crit.get("text"), "reason": reason,
                             "source_quote": crit.get("source_quote")})
            continue
        # Deterministic temporal gate. Two resolution cases, two different graded tasks:
        #   fix_before — a SEARCH/LINKING task: the fix already exists at report time, so the
        #     gradeable thing is correctly linking to the prior artifact (PR/commit/issue/
        #     version). Those identifiers are retrievable → knowable.
        #   fix_after  — a REMEDIATION-REASONING task: the specific fix is a future fact, but
        #     "what a correct fix must achieve / which direction it goes" is knowable by
        #     reasoning about the bug WITHOUT retrieving that fix. So only criteria that name
        #     the SPECIFIC future fix (exact PR/commit/version/advisory) are gated out;
        #     remediation criteria derived from the diff stay knowable.
        loc = (crit.get("source_loc") or "").lower()
        text = (crit.get("text") or "").lower()
        names_specific_fix = (
            loc in ("hard_facts", "advisory")
            or "points to the fix" in text or "point to the fix" in text
            or "identifies the fix" in text or "identifies the existing fix" in text
            or "cites the fix" in text
        )
        if resolution_case == "fix_after" and names_specific_fix:
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
def call_litellm(prompt, model, system, api_base=None):
    import litellm
    # Use ollama's CHAT endpoint, not the generate endpoint: the generate path returns
    # empty content for some models (e.g. gpt-oss) under JSON mode.
    if model.startswith("ollama/"):
        model = "ollama_chat/" + model[len("ollama/"):]
    kwargs = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": prompt}],
        "max_tokens": 8192,
        "response_format": {"type": "json_object"},
    }
    # Only local ollama models take a custom temperature; reasoning models
    # (gpt-5.x, o-series) reject any value but the default.
    if model.startswith("ollama_chat/"):
        kwargs["temperature"] = 0.2
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
                sysprompt = system_prompt(record.get("resolution_case"))
                draft = call_litellm(build_prompt(record, qa), args.model, sysprompt, args.api_base)
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
