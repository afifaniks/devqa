"""
Stage 1 — Question normalization for the SecDevQA evaluation harness.

Reads the benchmark JSONL and, for each pair, drafts a canonical, self-contained
eval_question using an LLM (default: gpt-4o via LiteLLM).

Output:
  eval/data/eval_questions.jsonl  — one record per benchmark pair
  eval/data/eval_questions_review.md — human-readable side-by-side review file

Records in eval_questions.jsonl:
  id, eval_question, question_source, reporter_cited_identifiers, leak_flags,
  needs_human_review, normalizer_model, approved (always False — human must set True)

Usage:
  python -m eval.normalize_questions --benchmark dataset/security_benchmark.jsonl
  python -m eval.normalize_questions --force       # re-draft all, overwrite
  python -m eval.normalize_questions --mock        # stub LLM, no API key needed
"""

import argparse
import json
import sys
import time
from pathlib import Path

import litellm
from dotenv import load_dotenv

load_dotenv()

from eval.config import (DATA_DIR, DEFAULT_BENCHMARK, EVAL_QUESTIONS_FILE,
                         NORMALIZER_MODEL, NORMALIZER_PROMPT)
from eval.data import (build_thread_text, find_hard_fact_leaks,
                       find_reporter_cited_identifiers, get_question_comment,
                       load_benchmark, question_source, validate_benchmark_row)

MOCK_EVAL_QUESTION = (
    "Is this a genuine security vulnerability in this library, and if so, "
    "which version or configuration is affected and how should it be mitigated?"
)


def draft_eval_question(
    row: dict,
    model: str,
    mock: bool = False,
) -> tuple[str, list[str], bool]:
    """
    Call the LLM to draft an eval_question for the given benchmark row.

    Returns (eval_question, reporter_cited_identifiers, needs_human_review).
    Raises on non-retryable failures (caller logs error record instead).
    """
    if mock:
        q_comment = get_question_comment(row)
        cited = find_reporter_cited_identifiers(q_comment["body"])
        return MOCK_EVAL_QUESTION, cited, True

    thread_text = build_thread_text(row)
    user_message = thread_text

    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": NORMALIZER_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
        max_tokens=2048,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON: {raw[:300]}") from exc

    eval_question = parsed.get("eval_question", "").strip()
    reporter_cited = parsed.get("reporter_cited_identifiers", [])
    needs_review = bool(parsed.get("needs_human_review", True))

    if not eval_question:
        raise ValueError("LLM returned empty eval_question")

    return eval_question, reporter_cited, needs_review


def normalize_questions(
    benchmark_path: Path,
    output_path: Path,
    model: str,
    force: bool,
    mock: bool,
    retry_errors: bool = False,
) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    rows = load_benchmark(benchmark_path)
    print(f"Loaded {len(rows)} benchmark pairs from {benchmark_path}")

    # Load already-processed IDs to support resumption
    existing: dict[str, dict] = {}
    if output_path.exists() and not force:
        with open(output_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    existing[rec["id"]] = rec
        print(f"Resuming: {len(existing)} already normalized, {len(rows) - len(existing)} remaining")

    # Validate all rows upfront — fail loud on structural problems
    for row in rows:
        try:
            validate_benchmark_row(row)
        except ValueError as exc:
            print(f"ERROR: malformed row — {exc}", file=sys.stderr)
            sys.exit(1)

    results: list[dict] = []
    errors = 0

    for i, row in enumerate(rows):
        pair_id = row["id"]

        # Skip if already done, unless --force (redo all) or --retry-errors (redo errored only)
        if pair_id in existing and not force:
            ex = existing[pair_id]
            if not (retry_errors and ex.get("error")):
                results.append(ex)
                continue

        print(f"[{i+1}/{len(rows)}] Normalizing {pair_id} ...", end=" ", flush=True)

        q_source = question_source(row)

        try:
            eval_q, reporter_cited, needs_review = draft_eval_question(row, model, mock=mock)
        except Exception as exc:
            print(f"ERROR: {exc}")
            errors += 1
            # Write an error record so we don't silently lose coverage
            results.append({
                "id": pair_id,
                "eval_question": None,
                "question_source": q_source,
                "reporter_cited_identifiers": [],
                "leak_flags": [],
                "needs_human_review": True,
                "normalizer_model": model,
                "approved": False,
                "error": str(exc),
            })
            continue

        leak_flags = find_hard_fact_leaks(eval_q, row["hard_facts"])

        rec = {
            "id": pair_id,
            "eval_question": eval_q,
            "question_source": q_source,
            "reporter_cited_identifiers": reporter_cited,
            "leak_flags": leak_flags,
            "needs_human_review": needs_review or bool(leak_flags),
            "normalizer_model": model,
            # mock mode: auto-approve stub questions for end-to-end wiring tests.
            # Real LLM runs always produce approved:false — human must set it.
            "approved": mock,
        }

        status = "WARN(leaks)" if leak_flags else ("REVIEW" if needs_review else "ok")
        print(status)
        results.append(rec)

        # Small delay between API calls to avoid rate limits
        if not mock and i < len(rows) - 1:
            time.sleep(0.5)

    # Write JSONL output
    with open(output_path, "w", encoding="utf-8") as fh:
        for rec in results:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    n_ok = sum(1 for r in results if r.get("eval_question") and not r.get("error"))
    n_leaks = sum(1 for r in results if r.get("leak_flags"))
    n_needs_review = sum(1 for r in results if r.get("needs_human_review"))

    print(f"\nDone: {n_ok}/{len(rows)} normalized, {errors} errors, "
          f"{n_leaks} with leak flags, {n_needs_review} flagged for human review")
    print(f"Output: {output_path}")
    print("\nNext: open the review file, edit eval_question drafts as needed, "
          "then set approved:true in eval_questions.jsonl for each accepted pair.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage 1: Normalize benchmark questions into canonical eval_questions."
    )
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=DEFAULT_BENCHMARK,
        help=f"Path to benchmark JSONL (default: {DEFAULT_BENCHMARK})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=EVAL_QUESTIONS_FILE,
        help=f"Output eval_questions.jsonl (default: {EVAL_QUESTIONS_FILE})",
    )
    parser.add_argument(
        "--model",
        default=NORMALIZER_MODEL,
        help=f"LiteLLM model string for drafting (default: {NORMALIZER_MODEL})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-draft all questions, overwriting existing output",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use stub LLM responses — no API key required (for wiring tests)",
    )
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Re-draft only pairs that previously errored (eval_question is null)",
    )
    args = parser.parse_args()

    normalize_questions(
        benchmark_path=args.benchmark,
        output_path=args.output,
        model=args.model,
        force=args.force,
        mock=args.mock,
        retry_errors=args.retry_errors,
    )


if __name__ == "__main__":
    main()
