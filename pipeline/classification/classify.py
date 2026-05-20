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
- General concern, opinion, or discussion without a specific question and answer
- The question is a part of bug report template or feature request template that is not actually asking a question
- The answer is instructional — it tells you how to do, configure, or fix
  something, rather than informing you about who, what, when, or why
  (e.g., "To attach a schema you can..." or "Here is a patch that fixes...")
- General discussion, opinions, or troubleshooting without a clear question and answer

ASSIGN OTHER only when:
- The answer is factual — it refers to people, code, commits, decisions, timelines,
  or explains past events about the codebase or team
- But the question does not match any Q1–Q78 specifically
- The technology came out after 2010, so it wouldn't have been studied by F&M, but the question is still about the codebase, team, or development process
- Be very strict about assigning OTHER — only when it's clearly a question with a clear answer, 
   but it doesn't fit any of the 78 F&M questions and "NONE" doesn't fit either.

{TAXONOMY_FOR_PROMPT}

Return only this JSON:
{{
  "question_id": "Q1"–"Q78", "OTHER", or "NONE",
  "question_source": "issue_body" or "comment",
  "question_author": "GitHub username or empty string",
  "question_text": "verbatim question from the thread, or empty string if NONE",
  "question_comment_id": "cN ID or empty string",
  "answer_text": "specific answer, not the whole comment, or empty string if NONE",
  "answer_author": "GitHub username or empty string",
  "answer_comment_id": "cN ID or empty string",
  "answer_is_accepted": true or false,
  "confidence": 0.0 to 1.0,
  "reasoning": "one sentence"
}}"""

# ── Classifier ────────────────────────────────────────────────────────────────


def classify(thread_text, model):
    """Single-stage classification. Returns result dict or None on failure."""
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

    return {
        "contains_qa": True,
        "question_id": qid,
        "question_source": result.get("question_source", ""),
        "question_author": result.get("question_author", ""),
        "question_text": result.get("question_text", ""),
        "question_comment_id": result.get("question_comment_id", ""),
        "answer_text": result.get("answer_text", ""),
        "answer_author": result.get("answer_author", ""),
        "answer_comment_id": result.get("answer_comment_id", ""),
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
        threads_to_do = threads_to_do[:limit]

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
        thread_text = thread["thread_text"]
        result = classify(thread_text, model)

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
            "thread_text": thread_text,
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
