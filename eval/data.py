"""
Data loading and utilities for the SecDevQA evaluation harness.

Handles:
- Loading the benchmark JSONL (security_benchmark.jsonl)
- Extracting question/thread/answer comments from each row
- SHA-256 hashing of text content
- Regex patterns for the 8 hard-fact identifier types
- Detecting hard-fact leakage into drafted eval_questions
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Identifier regex patterns (8 types from benchmark hard_facts)
# Used both for reporter-citation detection and leak-checking.
# ---------------------------------------------------------------------------

IDENTIFIER_PATTERNS: dict[str, re.Pattern] = {
    "cve": re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.IGNORECASE),
    "ghsa": re.compile(r"\bGHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}\b", re.IGNORECASE),
    "osv": re.compile(r"\b(?:PYSEC|RUSTSEC|GHSA|GO|MAVEN|NPM|NUGET|PACKAGIST|PYPA|RUBYGEMS|OSV)-\d{4}-\d+\b", re.IGNORECASE),
    "cwe": re.compile(r"\bCWE-\d+\b", re.IGNORECASE),
    # Fix PRs: GitHub PR URL fragment or bare #NNN reference
    "fix_pr": re.compile(r"(?:pull/(\d+)|#(\d+))", re.IGNORECASE),
    # Fix commits: 40-char hex SHA or 7-12 char short SHA in plausible context
    "fix_commit": re.compile(r"\b([0-9a-f]{40}|[0-9a-f]{7,12})\b"),
    # Fixed versions: semver-ish patterns (e.g. 9.0.2, v2.3.1, 1.0.0-beta.1)
    "fixed_version": re.compile(r"\bv?\d+\.\d+(?:\.\d+)?(?:[-+][a-z0-9._-]*)?\b", re.IGNORECASE),
    # Advisory URLs: known advisory/vulnerability database domains
    "advisory_url": re.compile(
        r"https?://(?:"
        r"nvd\.nist\.gov|cve\.org|cvedetails\.com|"
        r"github\.com/advisories|ghsa\.github\.com|"
        r"osv\.dev|open\.cve\.io|"
        r"security\.snyk\.io|snyk\.io/vuln|"
        r"huntr\.dev|vuldb\.com"
        r")[^\s\)\"'<>]*",
        re.IGNORECASE,
    ),
}


def load_benchmark(path: Path | str) -> list[dict]:
    path = Path(path)
    rows = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed JSON at {path}:{lineno}: {exc}") from exc
    return rows


def get_comment_by_id(row: dict, comment_id: str) -> dict:
    for c in row["comments"]:
        if c["id"] == comment_id:
            return c
    raise KeyError(f"Comment {comment_id!r} not found in row {row['id']!r}")


def get_question_comment(row: dict) -> dict:
    return get_comment_by_id(row, row["question_comment_id"])


def get_answer_comment(row: dict) -> dict:
    return get_comment_by_id(row, row["answer_comment_id"])


def get_thread_before_answer(row: dict) -> list[dict]:
    """Return all comments up to (not including) the answer comment."""
    answer_id = row["answer_comment_id"]
    thread = []
    for c in row["comments"]:
        if c["id"] == answer_id:
            break
        thread.append(c)
    return thread


def question_source(row: dict) -> str:
    return "issue_body" if row["question_comment_id"] == "c0" else "thread_comment"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def find_reporter_cited_identifiers(text: str) -> list[str]:
    """Find all hard-fact-style identifiers present in reporter text."""
    found = set()
    for name, pat in IDENTIFIER_PATTERNS.items():
        if name in ("fix_commit", "fixed_version"):
            # Too many false positives in freeform text; only include CVE/GHSA/OSV/CWE/advisory
            continue
        for m in pat.finditer(text):
            found.add(m.group(0))
    return sorted(found)


def find_hard_fact_leaks(draft: str, hard_facts: dict) -> list[str]:
    """
    Return any hard_facts values that appear verbatim in the draft text.
    Used to flag potential answer leakage in the LLM-drafted eval_question.
    """
    leaked = []
    for field, values in hard_facts.items():
        if not isinstance(values, list):
            continue
        for val in values:
            if not val:
                continue
            if str(val).lower() in draft.lower():
                leaked.append(f"{field}:{val}")
    return leaked


def load_eval_questions(path: Path | str) -> list[dict]:
    path = Path(path)
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


_BODY_MAX_CHARS = 8000  # guard against very long issue bodies truncating the LLM JSON response


def build_thread_text(row: dict) -> str:
    """Build human-readable thread text (minus answer) for the normalizer."""
    parts = [f"# Issue: {row['title']}", f"Repository: {row['repo']}", ""]
    for c in get_thread_before_answer(row):
        role_tag = f"[{c.get('role', 'comment')}]" if c.get("role") else ""
        parts.append(f"--- Comment {c['id']} by {c['author']} {role_tag} ---")
        body = c["body"]
        if len(body) > _BODY_MAX_CHARS:
            body = body[:_BODY_MAX_CHARS] + f"\n... [truncated — {len(c['body'])} chars total]"
        parts.append(body)
        parts.append("")
    return "\n".join(parts)


def validate_benchmark_row(row: dict) -> None:
    """Raise ValueError on structurally malformed rows."""
    required = ["id", "repo", "question_comment_id", "answer_comment_id", "comments", "hard_facts"]
    for field in required:
        if field not in row:
            raise ValueError(f"Row {row.get('id', '?')} missing field {field!r}")
    # Verify referenced comments exist
    get_question_comment(row)
    get_answer_comment(row)


def infer_provider(model_string: str) -> str:
    """Infer provider from LiteLLM model string prefix."""
    if "/" in model_string:
        return model_string.split("/")[0]
    # No prefix → OpenAI
    return "openai"
