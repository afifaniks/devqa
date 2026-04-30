"""
Classifies raw threads from raw_threads.jsonl into the taxonomy
using a local Ollama model.

Run as many times as you want — mining is already done.
Supports resuming, changing models, adjusting thresholds,
and re-running on already-classified threads with --force.

Usage:
  python classify_threads.py --repo pallets/flask
  python classify_threads.py --repo pallets/flask --model mistral:7b
  python classify_threads.py --repo pallets/flask --confidence 0.55
  python classify_threads.py --repo pallets/flask --force   # re-classify everything
  python classify_threads.py --repo pallets/flask --limit 100  # classify first 100 only
"""

import sys
import json
import os
import argparse
from collections import Counter
from tqdm import tqdm

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.storage import load_jsonl, append_record, load_checkpoint, save_checkpoint
from utils.ollama_client import generate_json, is_running, STAGE1_MODEL, STAGE2_MODEL
from config import REPOS

# ── Taxonomy ──────────────────────────────────────────────────────────────────

CATEGORIES = {
    "A": ("People & awareness", ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"]),
    "B": (
        "Code changes",
        [
            "Q8",
            "Q9",
            "Q10",
            "Q11",
            "Q12",
            "Q13",
            "Q14",
            "Q15",
            "Q16",
            "Q17",
            "Q18",
            "Q19",
            "Q20",
            "Q21",
            "Q22",
            "Q23",
            "Q24",
            "Q25",
            "Q26",
            "Q27",
        ],
    ),
    "C": ("Work item progress", ["Q28", "Q29", "Q30", "Q31"]),
    "D": ("Broken builds", ["Q32", "Q33", "Q34", "Q35"]),
    "E": ("Test cases", ["Q36", "Q37"]),
    "F": ("Pull requests", ["Q47", "Q48", "Q49", "Q50", "Q51", "Q52"]),
    "G": ("Bug management", ["Q53", "Q54", "Q55", "Q56", "Q57", "Q58", "Q59", "Q60"]),
    "H": ("CI/CD", ["Q61", "Q62", "Q63", "Q64"]),
    "I": ("Security & quality", ["Q65", "Q66", "Q67", "Q68"]),
    "J": ("Onboarding", ["Q69", "Q70", "Q71", "Q72"]),
    "K": ("Cross-artifact synthesis", ["Q73", "Q74", "Q75", "Q76", "Q77", "Q78"]),
}

QUESTIONS = {
    "Q1": "Who is currently working on a task or feature",
    "Q2": "What a specific coworker is working on right now",
    "Q3": "How much work a person has contributed",
    "Q4": "Who made a specific code change (person-focused)",
    "Q5": "Who has the knowledge to do a code review",
    "Q6": "What a person or team has been working on recently",
    "Q7": "Which code reviews are assigned to a specific person",
    "Q8": "How a piece of code has evolved over time",
    "Q9": "Why a specific change was introduced",
    "Q10": "Who made a change and why",
    "Q11": "Which classes or files a team has been editing",
    "Q12": "What changed in recently resolved work items related to someone",
    "Q13": "Who else is working on the same files",
    "Q14": "What changed between two builds and who changed it",
    "Q15": "Who has modified a specific file or class",
    "Q16": "Who is using an API that is about to change",
    "Q17": "Who originally created a specific API or component",
    "Q18": "Who most recently modified a file (latest owner)",
    "Q19": "Who modified a file most frequently (primary owner)",
    "Q20": "Who to contact about an unfamiliar part of the codebase",
    "Q21": "Which files or classes have changed recently",
    "Q22": "Which API methods have been added, changed, or removed",
    "Q23": "Which file or class has changed most frequently",
    "Q24": "Which code the asker worked on uses a specific pattern",
    "Q25": "Which code related to the asker has changed recently",
    "Q26": "How recent changes affect something the asker is building",
    "Q27": "What code is related to or affected by a specific change",
    "Q28": "What recent activity has happened on a specific issue",
    "Q29": "Which features or functions have been actively changing",
    "Q30": "Whether blocking issues in a milestone have been resolved",
    "Q31": "Whether work is progressing on planned items",
    "Q32": "What change or commit caused a build or test to fail",
    "Q33": "Who is responsible for breaking a build",
    "Q34": "Who most recently changed a failing test",
    "Q35": "Which specific changes caused test failures",
    "Q36": "Who owns or is responsible for a specific test",
    "Q37": "How tests relate to specific packages or classes",
    "Q47": "Who should review a specific PR",
    "Q48": "Why a PR was merged or rejected",
    "Q49": "Which PRs are blocking an issue from being resolved",
    "Q50": "How long PR review typically takes in an area",
    "Q51": "Which PRs have been waiting longest without review",
    "Q52": "Which bugs a PR is likely to fix",
    "Q53": "Whether a bug has been reported before (duplicate detection)",
    "Q54": "Who should be assigned to triage or fix a bug",
    "Q55": "Which file or component is responsible for a bug",
    "Q56": "Which commit introduced a regression",
    "Q57": "The severity or priority of a bug relative to others",
    "Q58": "Which bugs are related without being duplicates",
    "Q59": "How long bugs in an area typically take to fix",
    "Q60": "The full history and lifecycle of a bug",
    "Q61": "Whether a test failure is flaky or a real regression",
    "Q62": "Which CI stage or step is the bottleneck",
    "Q63": "How often a component causes build failures",
    "Q64": "Which contributor's changes most frequently break CI",
    "Q65": "Whether a change introduces a known vulnerability",
    "Q66": "Which dependencies have known vulnerabilities",
    "Q67": "Which parts of the codebase have low test coverage",
    "Q68": "Whether a patch follows security or style conventions",
    "Q69": "Where to start contributing to a specific component",
    "Q70": "What the unwritten conventions of the codebase are",
    "Q71": "Which issues are suitable for new contributors",
    "Q72": "What the contribution workflow looks like end to end",
    "Q73": "Given a stack trace, which recent commits are suspicious",
    "Q74": "Which developer has the most context on a specific bug",
    "Q75": "Which open bugs are likely to recur based on patterns",
    "Q76": "Why a PR was reverted given the full project context",
    "Q77": "Which changes historically co-occur with bugs in an area",
    "Q78": "What the blast radius of a change to a file would be",
}

SYSTEM_PROMPT = """You are a research assistant classifying GitHub threads 
for an academic study on developer information needs. Follow instructions 
precisely and return only valid JSON with no extra text."""


# ── Prompts ───────────────────────────────────────────────────────────────────


def build_stage1_prompt(thread_text):
    category_list = "\n".join(f"{k} - {v[0]}" for k, v in CATEGORIES.items())
    return f"""Read this GitHub thread.

<thread>
{thread_text[:10000]}
</thread>

Task: Does this thread contain a genuine developer information need AND a clear answer?

A genuine developer information need is a question about the development 
process itself — about people, code ownership, history, or process.

ACCEPT these:
- "Who owns this component?" → answered by naming a person
- "Which commit broke this?" → answered by pointing to a specific commit  
- "Who should review this?" → answered by suggesting a reviewer

REJECT these (mark as N):
- Bug reports: "I am getting this error" even if they end with "any ideas?"
- Feature requests: "Can you add support for X?"
- "Is this a bug?" or "Can this be fixed?" — these are support requests
- "Why does X not work?" — this is a bug report, not a process question
- Any thread where the "answer" is a code fix or workaround rather than 
  information about the development process
- Threads where the question is rhetorical or conversational

The question MUST be about: who, what, when, or why regarding the 
development process — not about how to use the library.

If yes, which broad category fits best?
{category_list}
N - Not a genuine developer information need

Return only this JSON:
{{"contains_qa": true or false, "category": "A" to "K" or "N", "confidence": 0.0 to 1.0}}"""


def build_stage2_prompt(thread_text, category_key):
    category_name, question_ids = CATEGORIES[category_key]
    question_list = "\n".join(f"{qid}: {QUESTIONS[qid]}" for qid in question_ids)
    return f"""Read this GitHub thread.

<thread>
{thread_text[:10000]}
</thread>

Category: {category_name}

Which specific question does this thread match?
{question_list}
NONE: Does not clearly match any of the above

Important: Choose NONE if:
- The question is about how to use the library, not about the development process
- The answer is a code snippet or workaround rather than process information
- The match requires stretching the question definition
- You are not confident the question and answer clearly align

Extract:
- question_source: "issue_body" if the question is in the issue body, "comment" if in a comment
- question_author: GitHub username of whoever asked
- question_text: exact phrasing from the thread, not a paraphrase
- answer_text: the specific answer, not the whole comment
- answer_author: GitHub username of whoever answered
- answer_is_accepted: true only if the issue was closed immediately after 
  this comment or the commenter explicitly resolved the question

Return only this JSON:
{{
  "question_id": "Q54" or "NONE",
  "question_source": "issue_body" or "comment",
  "question_author": "...",
  "question_text": "...",
  "answer_text": "...",
  "answer_author": "...",
  "answer_is_accepted": true or false,
  "confidence": 0.0 to 1.0,
  "reasoning": "one sentence"
}}"""


# ── Classifier ────────────────────────────────────────────────────────────────


def classify(thread_text, stage1_model, stage2_model):
    """Two-stage classification. Returns result dict or None on failure."""

    # Stage 1
    s1 = generate_json(
        build_stage1_prompt(thread_text),
        model=stage1_model,
        system=SYSTEM_PROMPT,
        max_tokens=150,
    )

    print(f"  [classify] stage 1 raw response: {s1}")

    if not s1 or not s1.get("contains_qa"):
        print(f"  [classify] stage 1: no Q&A detected")
        return {"contains_qa": False, "question_id": "NONE", "confidence": 0.0}

    category = s1.get("category", "N").upper()
    s1_confidence = float(s1.get("confidence", 0.0))

    if category == "N" or category not in CATEGORIES:
        return {
            "contains_qa": False,
            "question_id": "NONE",
            "confidence": s1_confidence,
        }

    # Stage 2
    s2 = generate_json(
        build_stage2_prompt(thread_text, category),
        model=stage2_model,
        system=SYSTEM_PROMPT,
        max_tokens=512,
    )

    print(f"  [classify] stage 2 raw response: {s2}")
    if not s2:
        return None

    return {
        "contains_qa": True,
        "question_id": s2.get("question_id", "NONE"),
        "question_text": s2.get("question_text", ""),
        "answer_text": s2.get("answer_text", ""),
        "answer_author": s2.get("answer_author", ""),
        "answer_is_accepted": s2.get("answer_is_accepted", False),
        "confidence": s1_confidence * float(s2.get("confidence", 0.0)),
        "reasoning": s2.get("reasoning", ""),
        "stage1_category": category,
    }


# ── Main ──────────────────────────────────────────────────────────────────────


def classify_threads(
    repo,
    stage1_model=STAGE1_MODEL,
    stage2_model=STAGE2_MODEL,
    confidence_threshold=0.55,
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

    # Checkpoint key includes model name so switching models re-classifies
    checkpoint_key = f"classify_{stage1_model}_{stage2_model}".replace(
        ":", "_"
    ).replace("/", "_")
    done = set() if force else load_checkpoint(repo, checkpoint_key)

    threads_to_do = [t for t in threads if t["number"] not in done]
    if limit:
        threads_to_do = threads_to_do[:limit]

    print(f"  threads total:     {len(threads)}")
    print(f"  already done:      {len(done)}")
    print(f"  to classify:       {len(threads_to_do)}")

    # Clear output file if force re-running
    if force:
        import os

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
        result = classify(thread_text, stage1_model, stage2_model)

        done.add(thread["number"])

        if result is None:
            failed += 1
            continue

        if not result.get("contains_qa"):
            skipped_no_qa += 1
            continue

        if result.get("question_id") == "NONE":
            skipped_no_qa += 1
            continue

        if result.get("confidence", 0) < confidence_threshold:
            skipped_low_confidence += 1
            continue

        record = {
            # Thread metadata
            "source": thread["source"],
            "repo": repo,
            "number": thread["number"],
            "title": thread.get("title", ""),
            "url": thread.get("url", ""),
            "created_at": thread.get("created_at", ""),
            # Classification results
            "question_id": result["question_id"],
            "question_text": result["question_text"],
            "answer_text": result["answer_text"],
            "answer_author": result["answer_author"],
            "answer_is_accepted": result.get("answer_is_accepted", False),
            "confidence": result["confidence"],
            "reasoning": result.get("reasoning", ""),
            "stage1_category": result.get("stage1_category", ""),
            # Keep original thread for manual review
            "thread_text": thread_text,
            # Classification metadata
            "stage1_model": stage1_model,
            "stage2_model": stage2_model,
        }

        results.append(record)
        counts[result["question_id"]] += 1
        append_record(repo, "natural_qa_pairs", record)

        if len(done) % 100 == 0:
            save_checkpoint(repo, checkpoint_key, done)

    save_checkpoint(repo, checkpoint_key, done)

    # Summary
    print(f"\n  results:")
    print(f"    classified:          {len(results)}")
    print(f"    no Q&A found:        {skipped_no_qa}")
    print(f"    low confidence:      {skipped_low_confidence}")
    print(f"    parse failures:      {failed}")
    print(f"\n  breakdown by question ID:")
    for qid, count in sorted(counts.items()):
        print(f"    {qid:5s}  {QUESTIONS.get(qid, '')[:50]:50s}  {count}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=None)
    parser.add_argument("--stage1-model", default=STAGE1_MODEL)
    parser.add_argument("--stage2-model", default=STAGE2_MODEL)
    parser.add_argument("--confidence", type=float, default=0.7)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only classify first N threads (for testing)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-classify all threads even if already done",
    )
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
