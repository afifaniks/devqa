"""
Evaluation harness configuration.

- MODELS: LiteLLM model registry for answer generation.
- SYSTEM_PROMPT: versioned prompt sent to models under test (no-context condition).
- NORMALIZER_PROMPT: prompt used to draft canonical eval_questions.

Cross-reference: research_plan_v6.md §4.1 (systems), §4.2 (context conditions),
§4.5 (contamination analysis).
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

EVAL_DIR = Path(__file__).parent
ROOT_DIR = EVAL_DIR.parent
DATA_DIR = EVAL_DIR / "data"
OUTPUT_DIR = EVAL_DIR / "output"

DEFAULT_BENCHMARK = ROOT_DIR / "dataset" / "security_benchmark.jsonl"
EVAL_QUESTIONS_FILE = DATA_DIR / "eval_questions.jsonl"
EVAL_QUESTIONS_REVIEW_MD = DATA_DIR / "eval_questions_review.md"

# ---------------------------------------------------------------------------
# Generation defaults
# ---------------------------------------------------------------------------

DEFAULT_TEMPERATURE = 0
DEFAULT_MAX_TOKENS = 2048
DEFAULT_NUM_RETRIES = 3
DEFAULT_N_SAMPLES = 1

# Model used by normalize_questions.py to draft eval_questions
NORMALIZER_MODEL = "gpt-5.4-mini"

# ---------------------------------------------------------------------------
# MODELS registry
# Each key is a LiteLLM model string (the value passed to litellm.completion).
# training_cutoff: ISO date string for contamination stratification (§4.5).
# max_tokens: per-model output cap (may override DEFAULT_MAX_TOKENS).
# provider: inferred from the LiteLLM prefix, but stored explicitly for
#           convenience (and for models with no prefix like OpenAI).
#
# How to add a model:
#   1. Add an entry here with the LiteLLM model string as the key.
#   2. Set training_cutoff to the model's knowledge cutoff (YYYY-MM-DD).
#   3. Ensure the corresponding env var is present in .env:
#      - OpenAI (no prefix):   OPENAI_API_KEY
#      - anthropic/ prefix:    ANTHROPIC_API_KEY
#      - gemini/ prefix:       GEMINI_API_KEY or GOOGLE_API_KEY
#      - ollama/ prefix:       no key; Ollama server must be running locally
# ---------------------------------------------------------------------------

MODELS: dict[str, dict] = {
    # --- OpenAI ---
    "gpt-5.4": {
        "provider": "openai",
        "training_cutoff": "2025-08-31",
        "max_tokens": DEFAULT_MAX_TOKENS,
    },
    "gpt-5.4-mini": {
        "provider": "openai",
        "training_cutoff": "2025-08-31",
        "max_tokens": DEFAULT_MAX_TOKENS,
    },
    # --- Anthropic ---
    "anthropic/claude-opus-4-7": {
        "provider": "anthropic",
        "training_cutoff": "2025-03-01",
        "max_tokens": DEFAULT_MAX_TOKENS,
    },
    "anthropic/claude-sonnet-4-6": {
        "provider": "anthropic",
        "training_cutoff": "2025-03-01",
        "max_tokens": DEFAULT_MAX_TOKENS,
    },
    "anthropic/claude-haiku-4-5-20251001": {
        "provider": "anthropic",
        "training_cutoff": "2025-01-01",
        "max_tokens": DEFAULT_MAX_TOKENS,
    },
    # --- Google Gemini ---
    "gemini/gemini-2.5-pro": {
        "provider": "gemini",
        "training_cutoff": "2025-01-01",
        "max_tokens": DEFAULT_MAX_TOKENS,
    },
    "gemini/gemini-2.5-flash": {
        "provider": "gemini",
        "training_cutoff": "2025-01-01",
        "max_tokens": DEFAULT_MAX_TOKENS,
    },
    # --- Ollama (open-weight, local) ---
    "ollama/qwen2.5:72b": {
        "provider": "ollama",
        "training_cutoff": "2024-09-01",
        "max_tokens": DEFAULT_MAX_TOKENS,
    },
    "ollama/llama3.3:70b": {
        "provider": "ollama",
        "training_cutoff": "2023-12-01",
        "max_tokens": DEFAULT_MAX_TOKENS,
    },
    "ollama/deepseek-r1:32b": {
        "provider": "ollama",
        "training_cutoff": "2025-01-01",
        "max_tokens": DEFAULT_MAX_TOKENS,
    },
    "ollama/qwen3:32b": {
        "provider": "ollama",
        "training_cutoff": "2025-03-01",
        "max_tokens": DEFAULT_MAX_TOKENS,
    },
}

# ---------------------------------------------------------------------------
# System prompt — sent to every model under test in the no-context condition.
# Version: v1. Hash this string for reproducibility tracking.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a security-knowledgeable assistant answering a developer's question about \
an open-source software project. You are operating under the no-context condition: \
you answer from your general training knowledge only. No source code, commits, \
advisories, or CVE records have been provided to you.

Instructions:
- Provide a direct, specific answer to the developer's question.
- Where you are confident, cite concrete identifiers: CVE IDs, GHSA IDs, fixed \
version numbers, fix commit hashes, or pull request numbers.
- If you are uncertain about a specific identifier, version, or fix detail, say so \
explicitly — incorrect specifics are more harmful than acknowledged uncertainty.
- If the question cannot be determined from your training knowledge, state that plainly.
- Do not pad with generic security advice unrelated to the question.
"""

# ---------------------------------------------------------------------------
# Normalizer prompt — used by normalize_questions.py to draft eval_questions.
# The LLM receives this as the system prompt; the user message is the thread.
# ---------------------------------------------------------------------------

NORMALIZER_PROMPT = """\
You are normalizing a GitHub issue thread into a self-contained, canonical question \
for a security evaluation benchmark.

Your task: produce an `eval_question` that captures what the developer is asking, \
without leaking any part of the maintainer's answer.

Requirements for `eval_question`:
1. SELF-CONTAINED — Must be intelligible without the thread. If the question is \
   mid-thread and references prior context ("the above issue", "this vulnerability", \
   "as mentioned"), resolve those references using the prior comments.
2. SITUATIONAL — Preserve the developer's specific situation: the library/package \
   name and version they use, their runtime/environment, what they observed or are \
   worried about, and the nature of their concern.
3. CODE AND POC — If the reporter included code snippets or a proof-of-concept, \
   keep them verbatim — they are part of how the question was posed.
4. REFRAME BUG REPORTS — If the body is a vulnerability disclosure or bug report \
   rather than an explicit question, reframe it as the developer's implicit question. \
   Examples: "Is this behavior a genuine security vulnerability in <library>?" / \
   "Does this affect my usage?" / "Which version introduces or fixes this?"
5. NO ANSWER LEAKAGE — Do not include the maintainer's answer. Exclude CVE IDs, \
   GHSA IDs, OSV IDs, CWE IDs, fix commit SHAs, fix PR references, fixed version \
   numbers, or advisory URLs that appear only in the maintainer's answer and not in \
   the reporter's own text. If the reporter themselves cited an identifier in their \
   own question, it may stay.
6. CONCISE — Remove boilerplate greetings, email signatures, and redundant repetition. \
   Preserve all technical substance.

Context provided to you: the issue title, the reporter's question text, and any prior \
thread comments that preceded the question (excluding the maintainer's answer).

Output ONLY a JSON object with this exact schema — no preamble, no markdown wrapper:
{
  "eval_question": "<canonical question — plain prose, code blocks preserved>",
  "reporter_cited_identifiers": ["<CVE/GHSA/OSV/CWE IDs, version numbers, commit SHAs, PR refs, or advisory URLs the REPORTER cited in their own question — not from the maintainer's answer; empty list if none>"],
  "needs_human_review": <true if: question is ambiguous, you made significant interpretive choices, the thread is complex, or you are unsure you correctly excluded answer content; otherwise false>
}
"""
