"""
Classifies raw threads from raw_threads.jsonl into the taxonomy
using a local Ollama model.

Single-stage: LLM picks Q-ID directly from the full F&M taxonomy.
Category is auto-derived from the question number (no LLM category step).

Usage:
  python classify.py --repo pallets/flask
  python classify.py --repo pallets/flask --model qwen2.5:14b
  python classify.py --repo pallets/flask --confidence 0.7
  python classify.py --repo pallets/flask --force
  python classify.py --repo facebook/react --limit 100
"""

import sys
import os
import random
import argparse
from collections import Counter
from tqdm import tqdm

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.storage import load_jsonl, append_record, load_checkpoint, save_checkpoint
from utils.ollama_client import generate_json, is_running, STAGE1_MODEL
from utils.taxonomy import QUESTIONS, QUESTION_TO_CATEGORY, TAXONOMY_FOR_PROMPT
from config import REPOS

DEFAULT_MODEL = STAGE1_MODEL

SYSTEM_PROMPT = """You are a research assistant classifying GitHub threads
for an academic study on developer information needs. Follow instructions
precisely and return only valid JSON with no extra text."""


# ── Prompt ────────────────────────────────────────────────────────────────────


def build_prompt(thread_text):
    return f"""Read this GitHub thread.

<thread>
{thread_text[:100000]}
</thread>

Task: Identify whether this thread contains a question a developer would ask
during their daily development work, and whether it has a clear answer.

This follows Fritz & Murphy (2010), who studied questions developers ask while
working — about their team, codebase, changes, builds, tests, and processes.

ASSIGN a Q-ID (Q1–Q78) if the thread contains a question that matches or very
similar to one of the F&M questions below and has a clear, informational answer.

ASSIGN NONE when any of the following apply:
- The thread contains no identifiable question with a clear answer
- Pure discussion, opinion, or back-and-forth with no specific question being asked
- The question is boilerplate from a bug report or feature request template and no
  developer is actually asking anything (e.g., "What is the current behavior?" as
  a template field, not a real question)
- No answer exists — thread was closed without a response, or only has "+1" / "me too"
  comments with no substantive reply

ASSIGN OTHER when the thread contains a clear developer question with a clear answer,
but the question does not match any Q1–Q78 specifically. This includes:
- How-to and usage questions ("How do I configure X?", "What is the right way to do Y?")
- Instructional answers are fine — "Use X instead", "You can fix this by..." count as answers
- Questions about technology that post-dates F&M (2010) but follows the same pattern
- Any Q&A about the codebase, team, or development process not covered by Q1–Q78
Be generous with OTHER: if there is a real question and a real answer, prefer OTHER over NONE.

DISAMBIGUATION — common confusions:
- Q14 vs Q48: Q14 = WHY was a design decision made (rationale explanation).
  Q48 = status/activity update ("fixed in #X", "closed via commit", "we plan to",
  "dropped in v3", "this has been resolved"). If the answer reports current state
  or an action taken — it is Q48, not Q14.
- "Is this behavior intentional?" → Q14 when the answer explains the design rationale.
- Q48 vs Q50/Q57: Q48 covers ALL single-issue status questions: "Is this fixed?",
  "Any updates?", "Are there plans to fix this?", "Has this been resolved?".
  Q50 = milestone-level blocker tracking across multiple items (rare in GitHub issues).
  Q57 = are active code commits being made on a plan item (rare; needs code evidence).
  When in doubt between Q48/Q50/Q57, prefer Q48.
- Q45 scope: Q45 = high-level activity summary of a subsystem/package ("what's
  changing in the auth/ package lately?"). NOT for "why does this package behave
  this way?" (→ Q14) and NOT for "is there a bug in this package?" (→ OTHER/Q59).

{TAXONOMY_FOR_PROMPT}

Each comment in the thread is tagged with an ID like [c0], [c1], [c2], etc.
Identify the comment that contains the question and the comment that contains
the answer by their IDs — the full comment text will be used verbatim.

Return only this JSON:
{{
  "question_id": "Q1"–"Q78", "OTHER", or "NONE",
  "other_question_type": "Only when question_id is OTHER: rephrase the core question as a short, developer-facing question (e.g. 'Is this behavior intentional?', 'How do I configure X?', 'What is the recommended approach for Y?', 'Will this PR be accepted?', 'When will this fix be released?', 'Is this a breaking change?', 'Does this version support X?', 'What is the team process for handling X?', 'How do I work around Z?'). Empty string otherwise.",
  "question_source": "issue_body" or "comment",
  "question_author": "GitHub username or empty string",
  "question_comment_id": "cN ID of the comment containing the question, or empty string",
  "answer_author": "GitHub username or empty string",
  "answer_comment_id": "cN ID of the comment containing the answer, or empty string",
  "answer_is_accepted": true or false,
  "confidence": 0.0 to 1.0,
  "reasoning": "one sentence"
}}"""

# ── Classifier ────────────────────────────────────────────────────────────────


def resolve_comment_body(comment_id, comment_lookup):
    """Return the verbatim body for a comment ID, or empty string if not found."""
    return comment_lookup.get(comment_id, "")


def classify(thread, model):
    """Single-stage classification. Returns result dict or None on failure."""
    thread_text = thread["thread_text"]
    comment_lookup = {c["id"]: c.get("body", "") for c in thread.get("comments", [])}
    if not comment_lookup:
        print(f"  [warn] thread #{thread.get('number')} has no comments dict — re-run mine_threads.py --force")

    result = generate_json(
        build_prompt(thread_text),
        model=model,
        system=SYSTEM_PROMPT,
        max_tokens=512,
    )

    print(f"  [classify] raw response: {result}")

    if not result:
        return None

    qid = result.get("question_id", "NONE")
    if not qid or qid == "NONE":
        return {
            "contains_qa": False,
            "question_id": "NONE",
            "confidence": float(result.get("confidence", 0.0)),
        }

    q_comment_id = result.get("question_comment_id", "")
    if not q_comment_id and result.get("question_source") == "issue_body":
        q_comment_id = "c0"
    a_comment_id = result.get("answer_comment_id", "")

    return {
        "contains_qa": True,
        "question_id": qid,
        "other_question_type": result.get("other_question_type", "") if qid == "OTHER" else "",
        "question_source": result.get("question_source", ""),
        "question_author": result.get("question_author", ""),
        "question_comment_id": q_comment_id,
        "question_text": resolve_comment_body(q_comment_id, comment_lookup),
        "answer_author": result.get("answer_author", ""),
        "answer_comment_id": a_comment_id,
        "answer_text": resolve_comment_body(a_comment_id, comment_lookup),
        "answer_is_accepted": result.get("answer_is_accepted", False),
        "confidence": float(result.get("confidence", 0.0)),
        "reasoning": result.get("reasoning", ""),
    }


# ── Main ──────────────────────────────────────────────────────────────────────


def classify_threads(
    repo,
    model=DEFAULT_MODEL,
    confidence_threshold=0.6,
    limit=None,
    force=False,
):
    if not is_running():
        print("  [error] Ollama is not running. Start with: ollama serve")
        return

    print(f"\n[classify_threads] {repo}")
    print(f"  model:      {model}")
    print(f"  confidence: {confidence_threshold}")

    threads = load_jsonl(repo, "raw_threads")
    if not threads:
        print("  [error] no raw_threads.jsonl found — run mine_threads.py first")
        return

    checkpoint_key = f"classify_{model}".replace(":", "_").replace("/", "_")
    seen_key = "classify_seen"
    if force:
        done = set()
    else:
        done = load_checkpoint(repo, checkpoint_key) | load_checkpoint(repo, seen_key)

    threads_to_do = [t for t in threads if t["number"] not in done]
    threads_to_do.sort(key=lambda t: t["number"], reverse=True)
    if limit:
        # threads_to_do = threads_to_do[:limit]
        # Randomly select threads to do, to get a more representative sample when testing
        threads_to_do = random.sample(threads_to_do, min(limit, len(threads_to_do)))

    print(f"  threads total:     {len(threads)}")
    print(f"  already done:      {len(done)}")
    print(f"  to classify:       {len(threads_to_do)}")

    if force:
        out_path = f"output/{repo.replace('/','__')}/natural_qa_pairs.jsonl"
        if os.path.exists(out_path):
            os.remove(out_path)
            print("  cleared previous results")

    results = []
    skipped_low_confidence = 0
    skipped_no_qa = 0
    failed = 0
    counts = Counter()

    for thread in tqdm(threads_to_do, desc="  classifying"):
        result = classify(thread, model)

        done.add(thread["number"])

        if result is None:
            failed += 1
            continue

        if not result.get("contains_qa"):
            skipped_no_qa += 1
            continue

        if result.get("confidence", 0) < confidence_threshold:
            skipped_low_confidence += 1
            continue

        qid = result["question_id"]
        category = QUESTION_TO_CATEGORY.get(qid, "")

        record = {
            # Thread metadata
            "source": thread["source"],
            "repo": repo,
            "number": thread["number"],
            "title": thread.get("title", ""),
            "url": thread.get("url", ""),
            "created_at": thread.get("created_at", ""),
            # Classification results
            "question_id": qid,
            "other_question_type": result.get("other_question_type", ""),
            "category": category,
            "question_source": result.get("question_source", ""),
            "question_author": result.get("question_author", ""),
            "question_text": result["question_text"],
            "question_comment_id": result.get("question_comment_id", ""),
            "answer_text": result["answer_text"],
            "answer_author": result["answer_author"],
            "answer_comment_id": result.get("answer_comment_id", ""),
            "answer_is_accepted": result.get("answer_is_accepted", False),
            "confidence": result["confidence"],
            "reasoning": result.get("reasoning", ""),
            # Keep original thread for manual review
            "thread_text": thread["thread_text"],
            "comments": thread.get("comments", []),
            # Classification metadata
            "model": model,
        }

        results.append(record)
        counts[qid] += 1
        append_record(repo, "natural_qa_pairs", record)

        if len(done) % 100 == 0:
            save_checkpoint(repo, checkpoint_key, done)
            save_checkpoint(repo, seen_key, done)

    save_checkpoint(repo, checkpoint_key, done)
    save_checkpoint(repo, seen_key, done)

    print(f"\n  results:")
    print(f"    classified:          {len(results)}")
    print(f"    no Q&A found:        {skipped_no_qa}")
    print(f"    low confidence:      {skipped_low_confidence}")
    print(f"    parse failures:      {failed}")
    print(f"\n  breakdown by question ID:")
    for qid, count in sorted(counts.items()):
        cat = QUESTION_TO_CATEGORY.get(qid, "?")
        print(f"    {qid:5s} [{cat}]  {QUESTIONS.get(qid, '')[:50]:50s}  {count}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--confidence", type=float, default=0.7)
    parser.add_argument("--limit", type=int, default=None,
                        help="Only classify first N threads (for testing)")
    parser.add_argument("--force", action="store_true",
                        help="Re-classify all threads even if already done")
    args = parser.parse_args()

    repos = [args.repo] if args.repo else REPOS
    for repo in repos:
        classify_threads(
            repo,
            model=args.model,
            confidence_threshold=args.confidence,
            limit=args.limit,
            force=args.force,
        )
