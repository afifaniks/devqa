"""
SecDevQA harness — shared LLM and JSONL utilities.

Kept inside the harness package so the benchmarking module has no dependency on the
benchmark-construction code (eval/, pipeline/): the harness only consumes the released
artifacts (dataset/security_benchmark_final.jsonl and the mined corpora under
output/<repo>/) as data files.
"""

from __future__ import annotations

import json
from pathlib import Path

import litellm
from dotenv import load_dotenv

load_dotenv()


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
    benchmark (dataset/security_benchmark_final.jsonl) keys threads by `id` and carries
    no approval gate — it is final, so every thread counts as approved. The older
    eval_pairs schema (`thread_id` + an `approved` flag) is left untouched."""
    threads = load_jsonl(path)
    for t in threads:
        if "thread_id" not in t and "id" in t:
            t["thread_id"] = t["id"]
        t.setdefault("approved", True)
    return threads


def chat_json(model: str, system: str, user: str, max_tokens: int = 6000) -> dict:
    """One JSON-mode completion (used by the judge)."""
    if model.startswith("ollama/"):
        model = "ollama_chat/" + model[len("ollama/"):]
    kwargs = dict(model=model,
                  messages=[{"role": "system", "content": system},
                            {"role": "user", "content": user}],
                  max_tokens=max_tokens, reasoning_effort="low",
                  response_format={"type": "json_object"})
    try:
        r = litellm.completion(temperature=0, **kwargs)
    except litellm.BadRequestError as exc:
        if "temperature" in str(exc).lower():
            r = litellm.completion(**kwargs)
        else:
            raise
    raw = (r.choices[0].message.content or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"non-JSON from {model}: {raw[:200]}") from exc
