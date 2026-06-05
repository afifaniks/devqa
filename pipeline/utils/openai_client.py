"""
OpenAI client (Responses API) with per-call token-usage capture.

generate_json() returns the parsed JSON (or None). If a `usage_log` list is
passed, one row {stage, input_tokens, cached_tokens, output_tokens} is appended
per API response. cached_tokens = prompt-cache hit (automatic for prompts
>= ~1024 tokens; grows when the static prompt prefix is identical across calls).
"""

import json

from openai import OpenAI

client = OpenAI()

STAGE1_MODEL = "gpt-5.4-mini"
STAGE2_MODEL = "gpt-5.4-mini"
# gpt-5-mini is a reasoning model and reasoning tokens count against
# max_output_tokens — keep effort minimal so a small budget isn't eaten.
REASONING_EFFORT = None

kwargs = {"reasoning": {"effort": REASONING_EFFORT}} if REASONING_EFFORT else {}

def generate_json(prompt, model=STAGE1_MODEL, system=None, max_tokens=2048,
                  usage_log=None, stage=None):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    for attempt in range(3):
        try:
            response = client.responses.create(
                model=model,
                input=messages,
                max_output_tokens=max_tokens,
                text={"format": {"type": "json_object"}},
                **kwargs                
            )

            if usage_log is not None:
                u = response.usage
                itd = getattr(u, "input_tokens_details", None)
                usage_log.append({
                    "stage": stage,
                    "input_tokens": u.input_tokens,
                    "cached_tokens": getattr(itd, "cached_tokens", 0) or 0,
                    "output_tokens": u.output_tokens,
                })

            text = response.output_text.strip()
            print(f"[openai] raw response: {text[:200]}")
            return json.loads(text)

        except Exception as e:
            print(f"[openai] attempt {attempt+1} failed: {e}")

    return None