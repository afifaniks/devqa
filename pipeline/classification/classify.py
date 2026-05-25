"""
Classifies raw threads from raw_threads.jsonl into the taxonomy
using a local Ollama model.

Two-stage: Stage 1 picks broad category (A–H or N), Stage 2 picks specific Q-ID.
Stage 2 can still emit OTHER or NONE as escapes.

Usage:
  python classify.py --repo pallets/flask
  python classify.py --repo pallets/flask --stage1-model qwen3.6:latest
  python classify.py --repo pallets/flask --stage2-model qwen2.5:14b
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
from utils.ollama_client import generate_json, is_running, STAGE1_MODEL, STAGE2_MODEL
from utils.taxonomy import CATEGORIES, PLAIN_TAXONOMY, QUESTIONS, QUESTION_TO_CATEGORY, CATEGORY_TAXONOMY
from config import REPOS

random.seed(777)

SYSTEM_PROMPT = """You are a research assistant classifying GitHub threads
for an academic study on developer information needs. Follow instructions
precisely and return only valid JSON with no extra text."""


# ── Stage 1 prompt ─────────────────────────────────────────────────────────────


def build_stage1_prompt(thread_text):
    category_list = "\n".join(f"{k} - {v[0]}" for k, v in CATEGORIES.items())
    valid_letters = "/".join(k for k in CATEGORIES.keys())
    return f"""You are an expert software engineer analyzing this thread to determine 
if it contains a clear developer question and answer.
    
Read this GitHub thread.

<thread>
{thread_text[:50000]}
</thread>


A developer information need is a question about:
- The team (who is working on what, who owns what, who knows what)
- The codebase (why something was changed, what changed, who changed it)
- Work item status (is this fixed, what is the progress, is this planned)
- Builds and tests (what is failing, what caused it)
- Development process (conventions, contribution, team organization)
- Software issues and failures (what is broken, why, and how to fix it)

Given the taxonomy of Fritz & Murphy (2010) and examples of type of questions in each category below, 
classify the thread into one of these high level categories (A–G, H, N) based on the main 
developer question being asked and answered in the thread.

{PLAIN_TAXONOMY}

CATEGORY H — valid developer Q&A outside the F&M taxonomy:
Use H only after confirming the thread does NOT fit A–G.
H is for questions about the development process or project internals with no A–G match:
Examples but not limited to:
- "What is the release timeline for v3?" / "Is this project still actively maintained?"
- "What is the convention for naming tests in this repo?"

CATEGORY N — not a developer information need. Use N when:
- There is no clear question being asked, you don't need to infer or imply a question
- A generic bug report with no specific question (e.g. "it doesn't work", "it crashes") and no informational answer
- Just a bug report with no question being asked in neither the issue body nor the comments
- Just a generic question from bug template but no real developer issue question being asked in the thread
- No direct and clear answer to the question
- No informational answer exists (closed with no response, only "+1" / "me too" comments)
- The only answer is a code patch or workaround with no explanation of WHY
- Pure feature request with nobody answering when / whether / why
- Template boilerplate with no real question being asked
- The question does not include enough information to be answerable (e.g. "it doesn't work" with no error message, steps, or details) 
or requires consecutive comments to piece together a question and answer (e.g. "it doesn't work" in one comment and then "here's the error message" in another comment, with no single comment containing a clear question or answer)

IMPORTANT: You must choose the best fitting category, even if it's not a perfect fit. If you're unsure, choose the category that seems most likely based on the content of the thread.
Your judgement should be based on the main question being asked in the thread, not on peripheral or minor questions/answers. 
If the thread contains multiple questions, classify based on the most central or important one.
A question-answer pair is valid if the question can be answered with information from the code, team, porject, documentation, or development process, and the answer provides that information in a clear way.

Return only this JSON:
{{"contains_qa": true or false, "category": "{valid_letters}", "confidence": "LOW" or "MEDIUM" or "HIGH"}}

confidence meaning: HIGH = clearly fits, MEDIUM = fits but uncertain, LOW = guessing.
Set contains_qa to true for A–H, false for N."""


# ── Stage 2 prompt ─────────────────────────────────────────────────────────────


def _build_disambiguation(category_key):
    if category_key == "C":
        return """
DISAMBIGUATION for category C:
- Q48 = status/activity update on a SINGLE issue or plan item. Use for:
  "Is this fixed?" / "Any updates?" / "Are there plans?" / "Was this closed?" / "Will this be in v3?"
- Q50 = milestone-level blocker tracking across MULTIPLE items (rare in GitHub issues).
- Q57 = specifically asking whether code commits are actively landing on a plan item (needs commit evidence).  
"""
    if category_key == "D":
        return """
DISAMBIGUATION for category D:
- Q59 = what change caused the build to break (change-focused).
- Q60 = cross-referencing the stack trace with change sets (analysis-focused).
- Q61 = who caused the build to break / who owns the broken tests (person-focused).
- Q63 = which specific changes caused test failures (change-set focused).
Thread identifies a specific commit/PR as cause → Q59 or Q63. Names a person → Q61.
"""
    return ""


def build_stage2_prompt(thread_text, category_key):
    category_name, question_ids = CATEGORIES[category_key]
    disambiguation = _build_disambiguation(category_key)

    if category_key == "H":
        task_block = (
            "Stage 1 flagged this as a valid developer Q&A outside the standard categories.\n"
            "Choose OTHER if it IS a real developer question or information need with a clear answer, "
            "NONE if stage 1 was wrong."
        )
        valid_ids = "OTHER or NONE"
    else:
        category_detail = CATEGORY_TAXONOMY.get(
            category_key,
            "\n".join(f"{qid}: {QUESTIONS[qid]}" for qid in question_ids),
        )
        task_block = (
            f"Which question ID best matches the thread?\n"
            f"Read each description and example carefully before choosing.\n\n"
            f"{category_detail}\n\n"
            f"OTHER: valid developer question or information need about {category_name.lower()}, "
            f"but none of the Q-IDs above match.\n"
            f"NONE: stage 1 was wrong — not a clear developer question or information need."
        )
        valid_ids = ", ".join(question_ids) + ", OTHER, or NONE"

    return f"""Read this GitHub thread.

<thread>
{thread_text[:50000]}
</thread>

Category from stage 1: {category_name}

{task_block}
{disambiguation}
Choose NONE only when:
- The question is about how to use the library, not the development process
- The only answer is a code snippet or patch with no informational explanation
- No clear question-answer pair exists in the thread

Choose OTHER (not NONE) when there IS a real developer information need
but no specific Q-ID above captures it.

Each comment in the thread is tagged [c0], [c1], [c2], etc.

Return only this JSON:
{{
  "question_id": {valid_ids!r},
  "other_question_type": "Only when question_id is OTHER: rephrase as a short developer-facing question. Empty string otherwise.",
  "question_source": "issue_body" or "comment",
  "question_author": "GitHub username or empty string",
  "question_comment_id": "cN ID of comment containing the question, or empty string",
  "answer_author": "GitHub username or empty string",
  "answer_comment_id": "cN ID of comment containing the answer, or empty string",
  "answer_is_accepted": true or false,
  "confidence": "LOW" or "MEDIUM" or "HIGH",
  "reasoning": "one sentence"
}}

confidence meaning: HIGH = this Q-ID clearly matches, MEDIUM = reasonable match, LOW = uncertain or forced."""


# ── Classifier ─────────────────────────────────────────────────────────────────


def resolve_comment_body(comment_id, comment_lookup):
    return comment_lookup.get(comment_id, "")


def classify(thread, stage1_model, stage2_model):
    """Two-stage classification. Returns result dict or None on failure."""
    thread_text = thread["thread_text"]
    comment_lookup = {c["id"]: c.get("body", "") for c in thread.get("comments", [])}
    if not comment_lookup:
        print(f"  [warn] thread #{thread.get('number')} has no comments dict — re-run mine_threads.py --force")

    # Stage 1 — broad category
    s1 = generate_json(
        build_stage1_prompt(thread_text),
        model=stage1_model,
        system=SYSTEM_PROMPT,
        max_tokens=250,
    )

    print(f"  [classify] stage 1 raw response: {s1}")

    if not s1 or not s1.get("contains_qa"):
        return {"contains_qa": False, "question_id": "NONE", "confidence": 0.0}

    _CONF = {"HIGH": 0.95, "MEDIUM": 0.75, "LOW": 0.5}
    category = s1.get("category", "N").upper()
    s1_confidence = _CONF.get(str(s1.get("confidence", "LOW")).upper(), 0.5)

    if category == "N" or category not in CATEGORIES:
        return {"contains_qa": False, "question_id": "NONE", "confidence": s1_confidence}

    # Stage 2 — specific Q-ID within category
    s2 = generate_json(
        build_stage2_prompt(thread_text, category),
        model=stage2_model,
        system=SYSTEM_PROMPT,
        max_tokens=512,
    )

    print(f"  [classify] stage 2 raw response: {s2}")

    if not s2:
        return None

    qid = s2.get("question_id", "NONE")
    if not qid or qid == "NONE":
        return {"contains_qa": False, "question_id": "NONE", "confidence": s1_confidence}

    q_comment_id = s2.get("question_comment_id", "")
    if not q_comment_id and s2.get("question_source") == "issue_body":
        q_comment_id = "c0"
    a_comment_id = s2.get("answer_comment_id", "")
    if a_comment_id and a_comment_id not in comment_lookup:
        print(f"  [warn] answer_comment_id {a_comment_id!r} not in comment_lookup — clearing")
        a_comment_id = ""

    return {
        "contains_qa": True,
        "question_id": qid,
        "other_question_type": s2.get("other_question_type", "") if qid == "OTHER" else "",
        "question_source": s2.get("question_source", ""),
        "question_author": s2.get("question_author", ""),
        "question_comment_id": q_comment_id,
        "question_text": resolve_comment_body(q_comment_id, comment_lookup),
        "answer_author": s2.get("answer_author", ""),
        "answer_comment_id": a_comment_id,
        "answer_text": resolve_comment_body(a_comment_id, comment_lookup),
        "answer_is_accepted": s2.get("answer_is_accepted", False),
        "stage1_confidence": str(s1.get("confidence", "LOW")).upper(),
        "stage2_confidence": str(s2.get("confidence", "LOW")).upper(),
        "confidence": s1_confidence * _CONF.get(str(s2.get("confidence", "LOW")).upper(), 0.5),
        "reasoning": s2.get("reasoning", ""),
        "stage1_category": category,
    }


# ── Main ───────────────────────────────────────────────────────────────────────


def classify_threads(
    repo,
    stage1_model=STAGE1_MODEL,
    stage2_model=STAGE2_MODEL,
    confidence_threshold=0.6,
    limit=None,
    force=False,
):
    if not is_running():
        print("  [error] Ollama is not running. Start with: ollama serve")
        return

    print(f"\n[classify_threads] {repo}")
    print(f"  models:     stage1={stage1_model}  stage2={stage2_model}")
    print(f"  confidence: {confidence_threshold}")

    threads = load_jsonl(repo, "raw_threads")
    if not threads:
        print("  [error] no raw_threads.jsonl found — run mine_threads.py first")
        return

    checkpoint_key = f"classify_{stage1_model}_{stage2_model}".replace(":", "_").replace("/", "_")
    seen_key = "classify_seen"
    if force:
        done = set()
    else:
        done = load_checkpoint(repo, checkpoint_key) | load_checkpoint(repo, seen_key)

    threads_to_do = [t for t in threads if t["number"] not in done]
    threads_to_do.sort(key=lambda t: t["number"], reverse=True)
    if limit:
        threads_to_do = random.sample(threads_to_do, min(limit, len(threads_to_do)))

    print(f"  threads total:     {len(threads)}")
    print(f"  already done:      {len(done)}")
    print(f"  to classify:       {len(threads_to_do)}")

    if force:
        out_path = f"output/{repo.replace('/','__')}/natural_qa_pairs_dual_stage.jsonl"
        if os.path.exists(out_path):
            os.remove(out_path)
            print("  cleared previous results")

    results = []
    skipped_low_confidence = 0
    skipped_no_qa = 0
    failed = 0
    counts = Counter()

    for thread in tqdm(threads_to_do, desc="  classifying"):
        result = classify(thread, stage1_model, stage2_model)

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
        category = QUESTION_TO_CATEGORY.get(qid, result.get("stage1_category", ""))

        record = {
            "source": thread["source"],
            "repo": repo,
            "number": thread["number"],
            "title": thread.get("title", ""),
            "url": thread.get("url", ""),
            "created_at": thread.get("created_at", ""),
            "question_id": qid,
            "other_question_type": result.get("other_question_type", ""),
            "category": category,
            "stage1_category": result.get("stage1_category", ""),
            "question_source": result.get("question_source", ""),
            "question_author": result.get("question_author", ""),
            "question_text": result["question_text"],
            "question_comment_id": result.get("question_comment_id", ""),
            "answer_text": result["answer_text"],
            "answer_author": result["answer_author"],
            "answer_comment_id": result.get("answer_comment_id", ""),
            "answer_is_accepted": result.get("answer_is_accepted", False),
            "stage1_confidence": result.get("stage1_confidence", ""),
            "stage2_confidence": result.get("stage2_confidence", ""),
            "confidence": result["confidence"],
            "reasoning": result.get("reasoning", ""),
            "thread_text": thread["thread_text"],
            "comments": thread.get("comments", []),
            "model": f"{stage1_model}+{stage2_model}",
        }

        results.append(record)
        counts[qid] += 1
        append_record(repo, "natural_qa_pairs_dual_stage", record)

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
    parser.add_argument("--stage1-model", default=STAGE1_MODEL)
    parser.add_argument("--stage2-model", default=STAGE2_MODEL)
    parser.add_argument("--confidence", type=float, default=0.7)
    parser.add_argument("--limit", type=int, default=None,
                        help="Randomly sample N threads (for testing)")
    parser.add_argument("--force", action="store_true",
                        help="Re-classify all threads even if already done")
    args = parser.parse_args()

    repos = [args.repo] if args.repo else REPOS
    for repo in repos:
        classify_threads(
            repo,
            stage1_model=args.stage1_model,
            stage2_model=args.stage2_model,
            confidence_threshold=args.confidence,
            limit=args.limit,
            force=args.force,
        )
