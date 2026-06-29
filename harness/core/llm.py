"""
SecDevQA harness — shared LLM helper.

Kept inside the harness package so the benchmarking module has no dependency on the
benchmark-construction code (eval/, pipeline/). Benchmark/JSONL loading lives in the
litellm-free harness.core.benchmark module; only the model call lives here.
"""

from __future__ import annotations

import json

import litellm
from dotenv import load_dotenv

load_dotenv()


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
