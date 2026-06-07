"""
Stage 2 — No-context answer generation for the SecDevQA evaluation harness.

For each (approved pair × model under test), sends the eval_question to the model
via LiteLLM and records the response. Grading is a separate future stage.

Cross-reference: research_plan_v6.md §4.2 (no-context condition), §4.5 (contamination).

Output: eval/output/answers_<run_id>.jsonl — one record per (pair, model, sample).

Record schema:
  pair_id, condition, model, provider, eval_question_hash, system_prompt_hash,
  response_text, usage, cost_usd, latency_s, temperature, n_sample_index,
  timestamp, git_rev, run_id, error

Usage:
  python -m eval.generate \\
      --questions eval/data/eval_questions.jsonl \\
      --models gpt-4o,anthropic/claude-sonnet-4-6 \\
      --run-id my-run \\
      --resume
  python -m eval.generate --mock    # wiring test, no API key
"""

import argparse
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import litellm
from dotenv import load_dotenv

load_dotenv()

from eval.config import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_N_SAMPLES,
    DEFAULT_NUM_RETRIES,
    DEFAULT_TEMPERATURE,
    MODELS,
    OUTPUT_DIR,
    SYSTEM_PROMPT,
)
from eval.data import infer_provider, load_eval_questions, sha256_text

CONDITION = "no_context"
MOCK_RESPONSE = (
    "[MOCK] This is a stub response generated without calling any API. "
    "It is used only for end-to-end wiring tests. Grading: future stage."
)


def _git_rev() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def _load_done_tuples(output_path: Path) -> set[tuple[str, str, int]]:
    """Return set of (pair_id, model, n_sample_index) already in output file."""
    done = set()
    if not output_path.exists():
        return done
    with open(output_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                done.add((rec["pair_id"], rec["model"], rec["n_sample_index"]))
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def _call_model(
    model: str,
    eval_question: str,
    temperature: float,
    max_tokens: int,
    num_retries: int,
    mock: bool,
) -> tuple[str, dict | None, float | None, float]:
    """
    Call the model and return (response_text, usage_dict, cost_usd, latency_s).
    Raises on non-retryable failure.
    """
    if mock:
        return MOCK_RESPONSE, None, None, 0.0

    t0 = time.monotonic()
    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": eval_question},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        num_retries=num_retries,
    )
    latency_s = time.monotonic() - t0

    response_text = response.choices[0].message.content or ""

    usage = None
    if response.usage:
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }

    cost_usd = None
    try:
        cost_usd = litellm.completion_cost(completion_response=response)
    except Exception:
        pass

    return response_text, usage, cost_usd, latency_s


def generate(
    questions_path: Path,
    model_list: list[str],
    output_path: Path,
    n_samples: int,
    resume: bool,
    mock: bool,
    run_id: str,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    num_retries: int = DEFAULT_NUM_RETRIES,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load and validate approved questions
    all_questions = load_eval_questions(questions_path)
    approved = [q for q in all_questions if q.get("approved") is True]

    if not approved:
        print(
            "ERROR: No approved questions found in eval_questions.jsonl.\n"
            "Run normalize_questions.py first, review the drafts, then set "
            "\"approved\": true for accepted pairs.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validate models — warn and skip unknown, but unknown is still valid for mock
    valid_models = []
    skipped_models = []
    for m in model_list:
        if m not in MODELS and not mock:
            # Still allow it — LiteLLM may support it; just warn
            print(f"WARNING: {m!r} not in MODELS registry — proceeding anyway")
        valid_models.append(m)

    if not valid_models:
        print("ERROR: no models to run", file=sys.stderr)
        sys.exit(1)

    done_tuples = _load_done_tuples(output_path) if resume else set()
    if resume and done_tuples:
        print(f"Resuming: {len(done_tuples)} (pair, model, sample) tuples already done")

    git_rev = _git_rev()
    system_prompt_hash = sha256_text(SYSTEM_PROMPT)

    total_planned = len(approved) * len(valid_models) * n_samples
    total_done_before = len(done_tuples)
    answered = 0
    errors_by_model: dict[str, list[str]] = {m: [] for m in valid_models}
    skipped_provider: dict[str, str] = {}

    print(f"Run ID: {run_id}")
    print(f"Questions: {len(approved)} approved | Models: {len(valid_models)} | "
          f"Samples: {n_samples} | Total calls: {total_planned}")
    print(f"Output: {output_path}")
    print()

    with open(output_path, "a", encoding="utf-8") as out_fh:

        for model in valid_models:
            provider = MODELS.get(model, {}).get("provider") or infer_provider(model)

            # Probe provider availability before iterating all questions
            if not mock and model not in skipped_provider:
                try:
                    _call_model(model, "ping", temperature, 16, 1, mock=False)
                except litellm.exceptions.AuthenticationError as exc:
                    reason = f"authentication failed ({exc})"
                    print(f"SKIP model {model!r}: {reason}")
                    skipped_provider[model] = reason
                    skipped_models.append((model, reason))
                    continue
                except litellm.exceptions.NotFoundError as exc:
                    reason = f"model not found ({exc})"
                    print(f"SKIP model {model!r}: {reason}")
                    skipped_provider[model] = reason
                    skipped_models.append((model, reason))
                    continue
                except litellm.exceptions.APIConnectionError as exc:
                    reason = f"API unreachable ({exc})"
                    print(f"SKIP model {model!r}: {reason}")
                    skipped_provider[model] = reason
                    skipped_models.append((model, reason))
                    continue
                except Exception:
                    pass  # Non-availability error on probe; proceed and fail per-pair

            for q in approved:
                pair_id = q["id"]
                eval_question = q["eval_question"]
                eval_question_hash = sha256_text(eval_question)

                for sample_idx in range(n_samples):
                    key = (pair_id, model, sample_idx)
                    if key in done_tuples:
                        continue

                    timestamp = datetime.now(timezone.utc).isoformat()
                    error_msg = None
                    response_text = None
                    usage = None
                    cost_usd = None
                    latency_s = None

                    try:
                        response_text, usage, cost_usd, latency_s = _call_model(
                            model, eval_question, temperature, max_tokens, num_retries, mock
                        )
                        answered += 1
                    except Exception as exc:
                        error_msg = str(exc)
                        errors_by_model[model].append(f"{pair_id}: {error_msg}")

                    rec = {
                        "pair_id": pair_id,
                        "condition": CONDITION,
                        "model": model,
                        "provider": provider,
                        "eval_question_hash": eval_question_hash,
                        "system_prompt_hash": system_prompt_hash,
                        "response_text": response_text,
                        "usage": usage,
                        "cost_usd": cost_usd,
                        "latency_s": latency_s,
                        "temperature": temperature,
                        "n_sample_index": sample_idx,
                        "timestamp": timestamp,
                        "git_rev": git_rev,
                        "run_id": run_id,
                        "error": error_msg,
                    }
                    out_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    out_fh.flush()

    # Summary
    total_errors = sum(len(v) for v in errors_by_model.values())
    print("\n" + "=" * 60)
    print("END-OF-RUN SUMMARY")
    print("=" * 60)
    print(f"Run ID:        {run_id}")
    print(f"Questions:     {len(approved)} approved")
    print(f"Models run:    {len(valid_models) - len(skipped_models)}")
    if skipped_models:
        print(f"Models skipped ({len(skipped_models)}):")
        for m, reason in skipped_models:
            print(f"  {m}: {reason}")
    print(f"Pairs answered: {answered}")
    print(f"Errors:        {total_errors}")
    if total_errors:
        for model, errs in errors_by_model.items():
            if errs:
                print(f"  {model}: {len(errs)} error(s)")
                for e in errs[:3]:
                    print(f"    {e}")
    print(f"Output:        {output_path}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage 2: No-context answer generation via LiteLLM."
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=None,
        help="Path to eval_questions.jsonl (default: eval/data/eval_questions.jsonl)",
    )
    parser.add_argument(
        "--models",
        default=None,
        help="Comma-separated LiteLLM model strings (default: all in MODELS registry)",
    )
    parser.add_argument(
        "--n-samples",
        type=int,
        default=DEFAULT_N_SAMPLES,
        help=f"Repeated samples per pair (default: {DEFAULT_N_SAMPLES})",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run identifier (default: UTC timestamp)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip (pair, model, sample) tuples already in the output file",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use stub completions — no API key required (for wiring tests)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
    )
    args = parser.parse_args()

    from eval.config import EVAL_QUESTIONS_FILE

    questions_path = args.questions or EVAL_QUESTIONS_FILE
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = args.output_dir / f"answers_{run_id}.jsonl"

    if args.models:
        model_list = [m.strip() for m in args.models.split(",") if m.strip()]
    else:
        model_list = list(MODELS.keys())

    generate(
        questions_path=questions_path,
        model_list=model_list,
        output_path=output_path,
        n_samples=args.n_samples,
        resume=args.resume,
        mock=args.mock,
        run_id=run_id,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )


if __name__ == "__main__":
    main()
