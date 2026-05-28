"""
Open-coded Q&A detection pipeline (Track B, Stage 1+2).

Stage 1: Detect whether thread contains a valid developer information need.
         Emits free-text need_summary — no fixed enum, for later axial coding.
Stage 2: Extract verbatim Q, verbatim A, artifacts needed, answerer role,
         and verifiability tag.

Output: output/<owner>__<repo>/open_qa_pairs.jsonl

Usage:
  python detect_qa.py --repo psf/requests
  python detect_qa.py --repo psf/requests --model qwen3.6:latest
  python detect_qa.py --repo psf/requests --limit 100 --force
"""

import sys
import os
import random
import argparse
from tqdm import tqdm

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.storage import load_jsonl, append_record, load_checkpoint, save_checkpoint
from utils.ollama_client import generate_json, is_running, STAGE1_MODEL
from config import REPOS

random.seed(777)

SYSTEM_PROMPT = """You are a research assistant analyzing GitHub threads
for an academic study on developer information needs. Follow instructions
precisely and return only valid JSON with no extra text."""

ARTIFACT_OPTIONS = [
    "code",
    "commit_history",
    "issue_tracker",
    "pr_data",
    "ci_logs",
    "contributor_data",
    "documentation",
    "external_reference",
    "none",
    "other"
]


# ── Stage 0: Rule-based pre-filter ────────────────────────────────────────────


def prefilter(thread) -> bool:
    """Drop threads that cannot contain a valid Q&A before hitting the LLM."""
    comments = thread.get("comments", [])

    # Need at least two non-bot participants with substantive content
    non_bot = [
        c for c in comments
        if not any(sig in (c.get("author") or "") for sig in ("[bot]", "-bot"))
        and len((c.get("body") or "").strip()) > 20
    ]
    return len(non_bot) >= 2


# ── Stage 1: Detection ────────────────────────────────────────────────────────


def build_detection_prompt(thread_text):
    return f"""Read this GitHub thread and determine if it contains a valid developer information need.

<thread>
{thread_text[:50000]}
</thread>

A VALID developer information need is a question about:
- The codebase: why something was changed, what changed, who changed it, design rationale
- The team or process: who owns what, who to talk to, contribution conventions
- Work item status: is this bug fixed, is this behavior intentional, what is the plan
- Builds and tests: what is failing, why did this break, what caused it
- Project history and decisions: why was this architecture chosen, what was the motivation

NOT VALID — reject these:
- End-user how-to questions: "How do I configure X?", "How can I use Y?", "Does this support Z?"
  These ask about how to USE the library, not about the project's development or internals.
- Bug reports with no answer: "it crashes" with no substantive explanation of cause
- No-reply threads: closed with no response, only "+1" or "me too" comments
- Template boilerplate with no real question
- Pure feature requests with no answer about whether/when/why
- Threads where the only response is a code patch with no explanation of why

VALID examples:
- "Why was this behavior changed in v3?" + maintainer explains the design rationale ✓
- "Is this bug fixed?" + "Yes, merged in PR #1234 in v2.1" ✓
- "What caused the build to break?" + explanation of which change caused it ✓
- "Is this behavior intentional?" + "Yes, because we need X to avoid Y" ✓
- Feature request + "we plan to add this in v4" → valid (status answer) ✓
- Bug report + maintainer explains root cause even without a fix → valid ✓

If valid, write ONE SENTENCE summarizing what information the developer needed to know.
Write it as a plain English developer question. Do NOT use taxonomy terms or category labels.
Good summaries:
- "Why was the connection pooling behavior changed to reject idle connections after 30 seconds?"
- "Whether the project plans to support Python 3.12 and when."
- "What caused the nightly build to fail after the recent dependency upgrade."
- "Whether the missing TypeScript definition for StripeError is intentional or a bug."

Return only this JSON:
{{"contains_qa": true or false, "need_summary": "one sentence or empty string", "confidence": "HIGH" or "MEDIUM" or "LOW"}}

confidence: HIGH = clear Q&A with a clear informative answer, MEDIUM = valid but answer partial or indirect, LOW = borderline."""


# ── Stage 2: Extraction ───────────────────────────────────────────────────────


def build_extraction_prompt(thread_text):
    artifact_list = ", ".join(f'"{a}"' for a in ARTIFACT_OPTIONS)
    return f"""Read this GitHub thread and extract the core question-answer pair.

<thread>
{thread_text[:50000]}
</thread>

Each comment is tagged [c0], [c1], [c2], etc. c0 is the issue or PR body.

Your task:
1. QUESTION TEXT — copy the exact wording of the key question from the thread.
   Use the comment ID (cN) to locate it. The question is the sentence or paragraph
   that most clearly states the information need.

2. ANSWER TEXT — copy the exact wording of the best answer. Must be substantive
   (a full sentence or more with real information, not just "yes" or a code snippet).

3. ARTIFACTS NEEDED — which project artifacts would a tool need to answer this question?
   Choose from: {artifact_list}
   Be specific: if the answer requires knowing who last committed to a file, include
   "commit_history". If it requires reading the source code, include "code". If it can be answered from docs or issue comments, include "documentation" or "issue_tracker". 
   If it requires external research, include "external_reference". If no artifacts are needed and the answer is fully in the thread, say "none". 
   If other specific artifacts are needed, list them as "other-{{artifact_type}}".

4. ANSWERER ROLE:
   - "maintainer" = has commit rights or is a core contributor
   - "contributor" = has contributed before but not a core maintainer
   - "commenter" = community member with no known project contribution
   - "bot" = automated response

5. VERIFIABILITY:
   - "hard" = answer is a specific checkable fact (commit SHA, PR number, person's name,
     version number, file path) — an LLM could be graded right/wrong objectively
   - "soft" = answer is partially verifiable (general statement about a plan, behavior,
     or convention — checkable against docs or issues but not a single artifact)
   - "judgment" = answer is a design rationale, opinion, or architectural decision
     that cannot be objectively verified

Return only this JSON:
{{
  "question_comment_id": "cN tag where the question appears, e.g. c0",
  "question_author": "GitHub username or empty string",
  "question_text": "verbatim question text from the thread",
  "answer_comment_id": "cN tag where the best answer appears",
  "answer_author": "GitHub username or empty string",
  "answer_text": "verbatim answer text from the thread",
  "artifacts_needed": ["list", "of", "artifact", "types"],
  "answerer_role": "maintainer or contributor or commenter or bot",
  "verifiability": "hard or soft or judgment",
  "confidence": "HIGH or MEDIUM or LOW",
  "reasoning": "one sentence explaining why this is a valid developer information need"
}}"""


# ── Core detection function ───────────────────────────────────────────────────


_CONF = {"HIGH": 0.95, "MEDIUM": 0.75, "LOW": 0.5}


def detect_and_extract(thread, model):
    """Run Stage 1 + Stage 2. Returns result dict or None on parse failure."""
    thread_text = thread["thread_text"]
    comment_lookup = {c["id"]: c.get("body", "") for c in thread.get("comments", [])}

    # Stage 1 — detection
    s1 = generate_json(
        build_detection_prompt(thread_text),
        model=model,
        system=SYSTEM_PROMPT,
        max_tokens=300,
    )
    print(f"  [s1] {s1}")

    if not s1 or not s1.get("contains_qa"):
        return {"contains_qa": False}

    s1_conf = _CONF.get(str(s1.get("confidence", "LOW")).upper(), 0.5)
    need_summary = s1.get("need_summary", "").strip()

    # Stage 2 — extraction
    s2 = generate_json(
        build_extraction_prompt(thread_text),
        model=model,
        system=SYSTEM_PROMPT,
        max_tokens=600,
    )
    print(f"  [s2] {s2}")

    if not s2:
        return None

    q_comment_id = s2.get("question_comment_id", "c0")
    a_comment_id = s2.get("answer_comment_id", "")

    if q_comment_id not in comment_lookup and q_comment_id != "c0":
        q_comment_id = "c0"
    if a_comment_id and a_comment_id not in comment_lookup:
        print(f"  [warn] answer_comment_id {a_comment_id!r} not in lookup — clearing")
        a_comment_id = ""

    q_text = s2.get("question_text") or comment_lookup.get(q_comment_id, "")
    a_text = s2.get("answer_text") or comment_lookup.get(a_comment_id, "")

    if len(a_text.strip()) < 100:
        print(f"  [drop] answer too short ({len(a_text.strip())} chars)")
        return {"contains_qa": False}

    s2_conf = _CONF.get(str(s2.get("confidence", "LOW")).upper(), 0.5)

    return {
        "contains_qa": True,
        "need_summary": need_summary,
        "question_comment_id": q_comment_id,
        "question_author": s2.get("question_author", ""),
        "question_text": q_text,
        "answer_comment_id": a_comment_id,
        "answer_author": s2.get("answer_author", ""),
        "answer_text": a_text,
        "artifacts_needed": s2.get("artifacts_needed", []),
        "answerer_role": s2.get("answerer_role", "commenter"),
        "verifiability": s2.get("verifiability", "judgment"),
        "stage1_confidence": str(s1.get("confidence", "LOW")).upper(),
        "stage2_confidence": str(s2.get("confidence", "LOW")).upper(),
        "confidence": s1_conf * s2_conf,
        "reasoning": s2.get("reasoning", ""),
    }


# ── Main runner ───────────────────────────────────────────────────────────────


def run(repo, model=STAGE1_MODEL, confidence_threshold=0.5, limit=None, max_pairs=None, force=False, state_filter=None):
    if not is_running():
        print("  [error] Ollama not running — start with: ollama serve")
        return

    print(f"\n[detect_qa] {repo}")
    print(f"  model:      {model}")
    print(f"  threshold:  {confidence_threshold}")
    if state_filter:
        print(f"  state:      {state_filter}")

    if max_pairs and not force:
        existing = load_jsonl(repo, "open_qa_pairs")
        if existing and len(existing) >= max_pairs:
            print(f"  [skip] already have {len(existing)} pairs >= max_pairs={max_pairs}")
            return

    threads = load_jsonl(repo, "raw_threads")
    if not threads:
        print("  [error] no raw_threads.jsonl — run mine_threads.py first")
        return

    checkpoint_key = f"detect_qa_{model}".replace(":", "_").replace("/", "_")
    done = set() if force else load_checkpoint(repo, checkpoint_key)

    threads_to_do = [t for t in threads if t["number"] not in done]
    if state_filter:
        threads_to_do = [t for t in threads_to_do if t.get("state", "").lower() == state_filter]
    threads_to_do.sort(key=lambda t: t["number"], reverse=True)
    if limit:
        # threads_to_do = random.sample(threads_to_do, min(limit, len(threads_to_do)))
        threads_to_do = threads_to_do[:limit]

    print(f"  threads total:   {len(threads)}")
    print(f"  already done:    {len(done)}")
    print(f"  to process:      {len(threads_to_do)}")
    if max_pairs:
        print(f"  max pairs:       {max_pairs}")

    if force:
        out_path = f"output/{repo.replace('/','__')}/open_qa_pairs.jsonl"
        if os.path.exists(out_path):
            os.remove(out_path)
            print("  cleared previous output")

    existing_count = 0 if force else len(load_jsonl(repo, "open_qa_pairs") or [])
    accepted = existing_count
    dropped_prefilter = dropped_no_qa = dropped_conf = failed = 0

    for thread in tqdm(threads_to_do, desc="  detecting"):
        done.add(thread["number"])

        if not prefilter(thread):
            dropped_prefilter += 1
            continue

        result = detect_and_extract(thread, model)

        if result is None:
            failed += 1
            continue

        if not result.get("contains_qa"):
            dropped_no_qa += 1
            continue

        if result.get("confidence", 0) < confidence_threshold:
            dropped_conf += 1
            continue

        record = {
            "source": thread["source"],
            "repo": repo,
            "number": thread["number"],
            "title": thread.get("title", ""),
            "url": thread.get("url", ""),
            "state": thread.get("state", ""),
            "created_at": thread.get("created_at", ""),
            "question_id": "OPEN",
            "need_summary": result["need_summary"],
            "question_comment_id": result["question_comment_id"],
            "question_author": result["question_author"],
            "question_text": result["question_text"],
            "answer_comment_id": result["answer_comment_id"],
            "answer_author": result["answer_author"],
            "answer_text": result["answer_text"],
            "artifacts_needed": result["artifacts_needed"],
            "answerer_role": result["answerer_role"],
            "verifiability": result["verifiability"],
            "stage1_confidence": result["stage1_confidence"],
            "stage2_confidence": result["stage2_confidence"],
            "confidence": result["confidence"],
            "reasoning": result["reasoning"],
            "thread_text": thread["thread_text"],
            "comments": thread.get("comments", []),
            "model": model,
        }

        accepted += 1
        append_record(repo, "open_qa_pairs", record)

        if max_pairs and accepted >= max_pairs:
            done.add(thread["number"])
            print(f"  [stop] reached max_pairs={max_pairs}")
            break

        if len(done) % 50 == 0:
            save_checkpoint(repo, checkpoint_key, done)

    save_checkpoint(repo, checkpoint_key, done)

    new_accepted = accepted - existing_count
    print("\n  results:")
    print(f"    accepted (this run): {new_accepted}  (total: {accepted})")
    print(f"    pre-filter drop:     {dropped_prefilter}")
    print(f"    no Q&A found:        {dropped_no_qa}")
    print(f"    low confidence:      {dropped_conf}")
    print(f"    parse failures:      {failed}")
    yield_pct = int(100 * new_accepted / max(1, len(threads_to_do) - dropped_prefilter))
    print(f"    yield (post-filter): {yield_pct}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=None)
    parser.add_argument("--model", default=STAGE1_MODEL)
    parser.add_argument("--confidence", type=float, default=0.5,
                        help="Min confidence threshold (0–1, default 0.5)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Cap threads to process (for testing)")
    parser.add_argument("--max-pairs", type=int, default=None,
                        help="Stop after extracting N valid pairs")
    parser.add_argument("--force", action="store_true",
                        help="Re-process all threads from scratch")
    parser.add_argument("--state", choices=["open", "closed"], default=None,
                        help="Filter threads by issue state (open or closed; default: all)")
    args = parser.parse_args()

    repos = [args.repo] if args.repo else REPOS
    for repo in repos:
        run(
            repo,
            model=args.model,
            confidence_threshold=args.confidence,
            limit=args.limit,
            max_pairs=args.max_pairs,
            force=args.force,
            state_filter=args.state,
        )
