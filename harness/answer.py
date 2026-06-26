"""
SecDevQA — Stage 2: run a model under test against normalized eval questions.

Reads the released benchmark dataset/security_benchmark_final.jsonl, flattens its qa_pairs,
and asks the candidate model each question under a controlled context condition. Responses
are written one-per-line and the run is resumable (already-answered qids are skipped unless
--force).

Conditions (research_plan_v6.md §4.2):
  * no_context       — question text only; model answers from training knowledge.   [implemented]
  * single_artifact  — question + primary artifact from artifacts_needed.            [Phase 4, see PLAN.md]
  * multi_artifact   — question + all artifacts in artifacts_needed (oracle).        [Phase 4, see PLAN.md]
  * agent            — question + autonomous tool access; run via an agent harness,  [Phase 4, see PLAN.md]
                       not this script.

Usage:
  python -m harness answer --model openai/gpt-5.4-mini
  python -m harness answer --model anthropic/claude-sonnet-4-6 --condition no_context
  python -m harness answer --model openai/gpt-5.4-mini --limit 3 --include-unapproved
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import litellm
from dotenv import load_dotenv

from harness.llm import load_jsonl, load_benchmark, default_benchmark

load_dotenv()

ROOT = Path(__file__).parent.parent
DEFAULT_INPUT = default_benchmark()
DEFAULT_OUTPUT_DIR = ROOT / "harness" / "output"

CONDITIONS = ("no_context", "single_artifact", "multi_artifact", "agent")
IMPLEMENTED_CONDITIONS = ("no_context",)

# System prompt for the model under test, no-context condition. The model must not be
# nudged toward the gold answer; it is told only the ground rules of the condition.
NO_CONTEXT_SYSTEM_PROMPT = """\
You are a security-knowledgeable assistant answering a developer's question about an \
open-source project. You are under a NO-CONTEXT condition: answer from your training \
knowledge only — no repository code, commits, issues, or advisory documents are provided.

Give a direct, specific answer. Cite concrete identifiers (CVE/GHSA IDs, versions, \
commits) only when you are confident they are correct; acknowledge uncertainty rather \
than guess. If the question cannot be determined without project-specific information \
you do not have, say so explicitly. No generic padding."""


def slugify(model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", model).strip("-")


def complete(model: str, system: str, user: str, max_tokens: int) -> tuple[str, dict]:
    """One candidate completion. Returns (text, usage). temperature=0 where supported."""
    if model.startswith("ollama/"):
        model = "ollama_chat/" + model[len("ollama/"):]
    kwargs = dict(model=model,
                  messages=[{"role": "system", "content": system},
                            {"role": "user", "content": user}],
                  max_tokens=max_tokens)
    try:
        r = litellm.completion(temperature=0, **kwargs)
    except litellm.BadRequestError as exc:
        if "temperature" in str(exc).lower():
            r = litellm.completion(**kwargs)
        else:
            raise
    usage = getattr(r, "usage", None)
    usage_d = {"prompt_tokens": getattr(usage, "prompt_tokens", None),
               "completion_tokens": getattr(usage, "completion_tokens", None)} if usage else {}
    return (r.choices[0].message.content or "").strip(), usage_d


def iter_items(threads: list[dict], include_unapproved: bool) -> list[tuple[dict, dict]]:
    """Flatten threads into (thread, qa_pair) items, approved threads only by default."""
    items = []
    for t in threads:
        if t.get("error") or not t.get("qa_pairs"):
            continue
        if not include_unapproved and not t.get("approved"):
            continue
        for p in t["qa_pairs"]:
            items.append((t, p))
    return items


def run(input_path: Path, output_dir: Path, model: str, condition: str,
        force: bool, limit: int | None, include_unapproved: bool,
        max_tokens: int) -> None:
    if condition not in IMPLEMENTED_CONDITIONS:
        raise SystemExit(
            f"Condition '{condition}' is not implemented yet (Phase 4 in PLAN.md). "
            f"Implemented: {', '.join(IMPLEMENTED_CONDITIONS)}")

    threads = load_benchmark(input_path)
    items = iter_items(threads, include_unapproved)
    if limit:
        items = items[:limit]
    if not items:
        raise SystemExit(f"No eval items found in {input_path}.")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"answers_{slugify(model)}_{condition}.jsonl"
    done: set[str] = set()
    if output_path.exists() and not force:
        done = {r["qid"] for r in load_jsonl(output_path) if not r.get("error")}
        print(f"Resuming: {len(done)} answers already in {output_path}")

    print(f"Model: {model} | condition: {condition} | items: {len(items)}")
    n_new = n_err = 0
    with open(output_path, "w" if force else "a", encoding="utf-8") as fh:
        for i, (thread, pair) in enumerate(items):
            qid = pair["qid"]
            if qid in done:
                continue
            print(f"[{i+1}/{len(items)}] {qid} ...", end=" ", flush=True)
            rec = {
                "qid": qid,
                "thread_id": thread["thread_id"],
                "repo": thread.get("repo"),
                "url": thread.get("url"),
                "condition": condition,
                "model": model,
                "knowledge_type": pair.get("knowledge_type"),
                "question": pair["question"],
                "answered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            try:
                text, usage = complete(model, NO_CONTEXT_SYSTEM_PROMPT,
                                       pair["question"], max_tokens)
                rec["response"] = text
                rec["usage"] = usage
                n_new += 1
                print(f"ok ({len(text)} chars)")
            except Exception as exc:
                rec["error"] = str(exc)
                n_err += 1
                print(f"ERROR: {exc}")
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            if i < len(items) - 1:
                time.sleep(0.3)

    print(f"\nDone: {n_new} new answers, {len(done)} skipped (already done), {n_err} errors")
    print(f"Output: {output_path}")
    print("Next: python -m harness grade --answers " + str(output_path))


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage 2: answer eval questions with a model.")
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                    help="benchmark jsonl with qa_pairs (default: security_benchmark_final.jsonl)")
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    ap.add_argument("--model", required=True,
                    help="LiteLLM model id, e.g. openai/gpt-5.4-mini, anthropic/claude-sonnet-4-6, ollama/qwen3.6:latest")
    ap.add_argument("--condition", choices=CONDITIONS, default="no_context")
    ap.add_argument("--limit", type=int, default=None, help="Answer only first N items")
    ap.add_argument("--include-unapproved", action="store_true",
                    help="Also answer items from threads not yet human-approved (smoke tests)")
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--force", action="store_true", help="Re-answer everything")
    args = ap.parse_args()
    run(args.input, args.output_dir, args.model, args.condition,
        args.force, args.limit, args.include_unapproved, args.max_tokens)


if __name__ == "__main__":
    main()
