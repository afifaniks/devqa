# SecDevQA Evaluation Harness — No-Context Condition

Answer-generation stage for the SecDevQA benchmark (ICSE 2027).  
Cross-reference: `research_plan_v6.md` §4.2 (no-context condition), §4.5 (contamination).

**Grading (LLM-as-judge) is a future stage.** This harness only generates and records model answers.

---

## Overview

```
normalize → [human review] → generate → [future: grade]
```

1. **Stage 1 (`normalize_questions.py`)**: draft canonical, self-contained `eval_questions` from the raw benchmark using an LLM. Write to `eval/data/eval_questions.jsonl`. Human reviews and sets `"approved": true`.
2. **Stage 2 (`generate.py`)**: for each approved question × model, call the model (no context — question text only) and record responses in `eval/output/answers_<run_id>.jsonl`.

---

## Setup

```bash
pip install -r eval/requirements.txt
```

Create a `.env` file at the project root with the API keys you need:

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...          # or GOOGLE_API_KEY
```

For Ollama models, no key is needed — start the server with `ollama serve` before running.

---

## Environment variables per provider

| Provider prefix | Env var |
|---|---|
| (none / OpenAI) | `OPENAI_API_KEY` |
| `anthropic/` | `ANTHROPIC_API_KEY` |
| `gemini/` | `GEMINI_API_KEY` or `GOOGLE_API_KEY` |
| `ollama/` | none — local server at `http://localhost:11434` |

---

## LiteLLM model strings and providers

All models are specified as LiteLLM model strings. The format is `[provider/]model-name`.

| LiteLLM string | Provider | Notes |
|---|---|---|
| `gpt-4o` | openai | no prefix needed for OpenAI |
| `gpt-4o-mini` | openai | |
| `o3` | openai | |
| `anthropic/claude-opus-4-7` | anthropic | |
| `anthropic/claude-sonnet-4-6` | anthropic | |
| `gemini/gemini-2.5-pro` | gemini | |
| `gemini/gemini-2.5-flash` | gemini | |
| `ollama/qwen2.5:72b` | ollama | requires local Ollama |
| `ollama/llama3.3:70b` | ollama | |
| `ollama/deepseek-r1:32b` | ollama | |

### How to add a model to the registry

Edit `eval/config.py` → `MODELS` dict:

```python
"provider/model-name": {
    "provider": "provider",          # openai, anthropic, gemini, ollama
    "training_cutoff": "YYYY-MM-DD", # for contamination stratification (§4.5)
    "max_tokens": 2048,
},
```

Then add the API key to `.env` if needed.

---

## Two-step run

### Step 1 — Normalize questions (one-time)

```bash
cd /path/to/dev-questions

# Draft eval_questions using gpt-4o (default):
python -m eval.normalize_questions --benchmark dataset/security_benchmark.jsonl

# Wiring test (no API key):
python -m eval.normalize_questions --mock

# Force re-draft:
python -m eval.normalize_questions --force
```

Output:
- `eval/data/eval_questions.jsonl` — one record per pair, `"approved": false`
- `eval/data/eval_questions_review.md` — side-by-side review file

**Human review step**: open `eval_questions_review.md`, review each drafted `eval_question`. For any pair you accept, open `eval_questions.jsonl` and change `"approved": false` → `"approved": true`. You may also edit the `eval_question` text directly in the JSONL before approving.

### Step 2 — Generate answers

```bash
# Run all models in the registry:
python -m eval.generate --resume

# Run a subset of models:
python -m eval.generate \
    --models gpt-4o,anthropic/claude-sonnet-4-6,gemini/gemini-2.5-pro,ollama/qwen2.5:72b \
    --run-id my-run \
    --resume

# Wiring test (no API keys, all models):
python -m eval.generate --mock
```

Output: `eval/output/answers_<run_id>.jsonl`

---

## Output schema — `answers_<run_id>.jsonl`

One JSON record per line, one record per (pair, model, sample_index):

| Field | Type | Description |
|---|---|---|
| `pair_id` | str | Benchmark pair ID (e.g. `"auth0/node-jsonwebtoken/issue/957"`) |
| `condition` | str | Always `"no_context"` in this stage |
| `model` | str | LiteLLM model string used |
| `provider` | str | Provider inferred from model string prefix |
| `eval_question_hash` | str | SHA-256 of the `eval_question` text |
| `system_prompt_hash` | str | SHA-256 of `SYSTEM_PROMPT` from `config.py` |
| `response_text` | str\|null | Model's raw response (null if error) |
| `usage` | obj\|null | `{prompt_tokens, completion_tokens, total_tokens}` (null if unavailable) |
| `cost_usd` | float\|null | Estimated cost from LiteLLM (null if unavailable) |
| `latency_s` | float\|null | Wall-clock seconds for the API call |
| `temperature` | float | Temperature used |
| `n_sample_index` | int | 0-based sample index (always 0 when `--n-samples 1`) |
| `timestamp` | str | ISO-8601 UTC timestamp of the call |
| `git_rev` | str\|null | Short git SHA at run time |
| `run_id` | str | Run identifier |
| `error` | str\|null | Error message if the call failed; null on success |

---

## Running tests

```bash
cd /path/to/dev-questions
python -m pytest eval/tests/ -v
```

---

## Reproducibility notes

- `system_prompt_hash` and `eval_question_hash` allow verifying that the exact same inputs were used across runs.
- `git_rev` pins the harness version.
- `temperature=0` is the default; at temperature 0, repeated runs should produce identical responses (provider permitting).
- Training cutoffs in `MODELS` enable contamination stratification: pre-cutoff vs. post-cutoff pair accuracy (§4.5).

---

## What this stage does NOT do

- **No grading.** Grading (LLM-as-judge against `hard_facts`) is a future stage that reads `answers_<run_id>.jsonl`.
- **No context injection.** The single-artifact and multi-artifact conditions are future stages.
- **No agent runs.** Agentic evaluation is a future stage.
