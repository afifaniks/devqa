"""
Open coding pipeline for security Q&A pairs.

Assigns inductive open codes to each Q&A pair in security_benchmark.jsonl.
Codes describe the type of security concern the question addresses.
Multiple codes per pair are expected.

Uses LiteLLM — supports any provider via its model string convention:
  ollama/qwen3.6:latest
  openai/gpt-4.1-mini
  anthropic/claude-sonnet-4-6
  gemini/gemini-2.5-flash
  ... (any LiteLLM-supported model)

Output: dataset/open_codes.jsonl  (one record per pair, resumable)

Usage:
    python open_coding/open_code.py --model openai/gpt-5.4-mini
    python open_coding/open_code.py --model anthropic/claude-sonnet-4-6
    python open_coding/open_code.py --model ollama/qwen3.6:latest
    python open_coding/open_code.py --model openai/gpt-5.4-mini --limit 10 --force
"""

import argparse
import json
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
INPUT_FILE = ROOT / "dataset" / "security_benchmark.jsonl"
OUTPUT_FILE = ROOT / "dataset" / "open_codes_gpt-5.4-mini.jsonl"

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a qualitative research assistant performing open coding on developer security Q&A pairs.

Open coding means: read the Q&A exchange, then assign short descriptive labels (codes) that capture the TYPE of security concern expressed. Codes should be:
- Descriptive, not evaluative
- Grounded in the text (use the developer's own words where possible)
- Specific enough to distinguish different concern types
- 2–6 words each (noun phrase preferred)

Each Q&A pair may receive 1–2 codes. Assign as many as are genuinely present; do not pad."""

CODING_TEMPLATE = """Q&A pair to code:

REPO: {repo}
ISSUE TITLE: {title}
ISSUE BODY (original post by {reporter}):
{issue_body}

SUMMARY: {qa_summary}
ARTIFACTS USED IN ANSWER: {artifacts_needed}
HARD FACTS (CVEs / CWEs / GHSAs / fixed versions / fix PRs): {hard_facts}

FULL THREAD (all comments, in order):
{thread}

--- focal exchange ---
QUESTION (by {question_author}):
{question}

ANSWER (by {answer_author}, role: {answerer_role}):
{answer}

---
Assign open codes to this Q&A pair. Return a JSON object with:
  "codes": list of 1–2 short code strings (noun phrases, 2–6 words each)
  "rationale": one sentence explaining how these codes were chosen

Example output:
{{
  "codes": ["dependency vulnerability disclosure", "transitive dependency risk"],
  "rationale": "The question asks whether a transitive dependency CVE affects this project and which version resolves it."
}}
Do not add more codes than are genuinely present and absolutely necessary.
Return only valid JSON. No markdown fences."""


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
def load_dataset(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def extract_qa_text(record: dict) -> tuple[str, str, str]:
    """Return (question_body, answer_body, formatted_thread)."""
    comments = record.get("comments", [])
    q_id = record["question_comment_id"]
    a_id = record["answer_comment_id"]
    by_id = {c["id"]: c for c in comments}
    q = by_id.get(q_id, {}).get("body", "").strip()
    a = by_id.get(a_id, {}).get("body", "").strip()
    parts = []
    for c in comments:
        tag = ""
        if c["id"] == q_id:
            tag = " [QUESTION]"
        elif c["id"] == a_id:
            tag = " [ANSWER]"
        parts.append(
            f"[{c['author']}{tag}]:\n{c['body'].strip()}"
        )
    thread = "\n\n".join(parts)
    return q, a, thread


def load_existing(path: Path) -> set[str]:
    done = set()
    if path.exists():
        with open(path) as f:
            for line in f:
                try:
                    done.add(json.loads(line)["id"])
                except Exception:
                    pass
    return done


def append_result(path: Path, record: dict) -> None:
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


# ---------------------------------------------------------------------------
# LiteLLM call
# ---------------------------------------------------------------------------
def call_litellm(prompt: str, model: str, api_base: str | None = None) -> dict | None:
    import litellm

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    kwargs = {
        "model": model,
        "messages": messages,
        "max_tokens": 2048,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    if api_base:
        kwargs["api_base"] = api_base

    for attempt in range(3):
        try:
            response = litellm.completion(**kwargs)
            text = response.choices[0].message.content.strip()

            # strip markdown fences if model adds them despite json_object mode
            if text.startswith("```"):
                parts = text.split("```")
                text = parts[1] if len(parts) > 1 else text
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            return json.loads(text)

        except json.JSONDecodeError as e:
            print(f"  [litellm] JSON parse failed attempt {attempt+1}: {e}")
        except Exception as e:
            print(f"  [litellm] attempt {attempt+1} failed: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)

    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def build_prompt(record: dict) -> str:
    q, a, thread = extract_qa_text(record)
    comments = record.get("comments", [])
    issue_body = comments[0]["body"].strip() if comments else ""
    hf = record.get("hard_facts", {})
    hard_facts_parts = []
    if hf.get("cve_ids"):
        hard_facts_parts.append("CVEs: " + ", ".join(hf["cve_ids"]))
    if hf.get("cwe_ids"):
        hard_facts_parts.append("CWEs: " + ", ".join(hf["cwe_ids"]))
    if hf.get("ghsa_ids"):
        hard_facts_parts.append("GHSAs: " + ", ".join(hf["ghsa_ids"]))
    if hf.get("fixed_versions"):
        hard_facts_parts.append("fixed in: " + ", ".join(hf["fixed_versions"]))
    if hf.get("fix_prs"):
        hard_facts_parts.append("fix PRs: " + ", ".join(hf["fix_prs"]))
    if hf.get("fix_commits"):
        hard_facts_parts.append("fix commits: " + ", ".join(hf["fix_commits"]))
    return CODING_TEMPLATE.format(
        repo=record.get("repo", ""),
        title=record.get("title", ""),
        reporter=record.get("reporter", "unknown"),
        issue_body=issue_body[:8192],
        qa_summary=record.get("qa_summary", ""),
        artifacts_needed=", ".join(record.get("artifacts_needed", [])) or "none",
        hard_facts="; ".join(hard_facts_parts) or "none",
        thread=thread[:50000],
        question_author=record.get("question_author", "unknown"),
        answer_author=record.get("answer_author", "unknown"),
        answerer_role=record.get("answerer_role", "unknown"),
        question=q[:8192],
        answer=a[:8192],
    )


def run(args):
    global INPUT_FILE, OUTPUT_FILE
    INPUT_FILE = Path(args.input)
    OUTPUT_FILE = Path(args.output)

    records = load_dataset(INPUT_FILE)
    if args.limit:
        records = records[: args.limit]

    done = set() if args.force else load_existing(OUTPUT_FILE)
    todo = [r for r in records if r["id"] not in done]

    print(f"Dataset : {len(records)} records")
    print(f"Coded   : {len(done)} already done")
    print(f"To code : {len(todo)}")
    print(f"Model   : {args.model}")
    print()

    if not todo:
        print("Nothing to do.")
        return

    errors = 0
    for i, record in enumerate(todo, 1):
        rec_id = record["id"]
        prompt = build_prompt(record)

        prompt_id = rec_id.replace("/", "_").replace("#", "_")
        with open(f"debug_prompt_{prompt_id}.txt", "w") as f:
            f.write(prompt)            

        print(f"[{i:3d}/{len(todo)}] {rec_id[:60]:<60} ... ", end="", flush=True)

        result = call_litellm(prompt, args.model, api_base=args.api_base or None)

        if result is None:
            print("FAILED")
            errors += 1
            continue

        codes = result.get("codes", [])
        rationale = result.get("rationale", "")

        if not isinstance(codes, list) or not codes:
            print(f"WARN: unexpected result: {result}")
            errors += 1
            continue

        out = {
            "id": rec_id,
            "repo": record.get("repo"),
            "codes": codes,
            "rationale": rationale,
            "model": args.model,
        }
        append_result(OUTPUT_FILE, out)
        print(f"OK  {codes}")

    print(f"\nDone: {len(todo) - errors} coded, {errors} errors")
    print(f"Output: {OUTPUT_FILE}")


def main():
    parser = argparse.ArgumentParser(
        description="Open coding pipeline — LiteLLM backend, any provider",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Model string examples (LiteLLM convention):
  openai/gpt-4.1-mini
  anthropic/claude-sonnet-4-6
  ollama/qwen3.6:latest          (needs --api-base http://localhost:11434)
  gemini/gemini-2.5-flash
        """,
    )
    parser.add_argument(
        "--model", required=True,
        help="LiteLLM model string, e.g. openai/gpt-4.1-mini or anthropic/claude-sonnet-4-6",
    )
    parser.add_argument(
        "--api-base", default=None,
        help="Optional API base URL (needed for Ollama: http://localhost:11434)",
    )
    parser.add_argument(
        "--input", default=str(INPUT_FILE),
        help=f"Input JSONL (default: {INPUT_FILE})",
    )
    parser.add_argument(
        "--output", default=str(OUTPUT_FILE),
        help=f"Output JSONL (default: {OUTPUT_FILE})",
    )
    parser.add_argument("--limit", type=int, default=0, help="Process only first N records (0 = all)")
    parser.add_argument("--force", action="store_true", help="Re-code already-coded records")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
