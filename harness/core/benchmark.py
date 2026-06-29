"""
SecDevQA harness — benchmark + JSONL loading.

Deliberately free of any LLM dependency (no litellm import) so the snapshot layer and
other lightweight consumers can resolve the eval source without pulling in the model
stack. The harness only consumes the released artifacts
(dataset/security_benchmark_*.jsonl and the mined corpora under output/<repo>/) as data.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness.core.paths import FINAL_BENCHMARK, RELEASE_BENCHMARK


def default_benchmark() -> Path:
    """The benchmark the harness evaluates over: the rubric-bearing release if it has
    been built, else the full final corpus."""
    return RELEASE_BENCHMARK if RELEASE_BENCHMARK.exists() else FINAL_BENCHMARK


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Bad JSON at {path}:{lineno}: {exc}") from exc
    return rows


def load_benchmark(path: Path) -> list[dict]:
    """Load the eval benchmark and normalize each thread so downstream code can rely
    on `thread_id` and `approved` regardless of the source schema. The released
    benchmark keys threads by `id` and carries no approval gate — it is final, so every
    thread counts as approved. The older eval_pairs schema (`thread_id` + an `approved`
    flag) is left untouched."""
    threads = load_jsonl(path)
    for t in threads:
        if "thread_id" not in t and "id" in t:
            t["thread_id"] = t["id"]
        t.setdefault("approved", True)
    return threads
