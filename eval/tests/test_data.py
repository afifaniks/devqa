"""Tests for eval/data.py — benchmark loading and utility functions."""

import json
import tempfile
from pathlib import Path

import pytest

from eval.data import (
    IDENTIFIER_PATTERNS,
    build_thread_text,
    find_hard_fact_leaks,
    find_reporter_cited_identifiers,
    get_answer_comment,
    get_question_comment,
    get_thread_before_answer,
    infer_provider,
    load_benchmark,
    question_source,
    sha256_text,
    validate_benchmark_row,
)

SAMPLE_ROW = {
    "id": "test/repo/issue/1",
    "repo": "test/repo",
    "number": 1,
    "title": "Test issue",
    "url": "https://github.com/test/repo/issues/1",
    "state": "closed",
    "created_at": "2024-01-01T00:00:00Z",
    "closed_at": "2024-01-02T00:00:00Z",
    "labels": [],
    "reporter": "alice",
    "security_topic": "test topic",
    "qa_summary": "test summary",
    "question_comment_id": "c0",
    "answer_comment_id": "c1",
    "question_author": "alice",
    "answer_author": "bob",
    "answerer_role": "maintainer",
    "artifacts_needed": ["code"],
    "hard_facts": {
        "cve_ids": ["CVE-2024-1234"],
        "ghsa_ids": ["GHSA-abcd-efgh-ijkl"],
        "cwe_ids": ["CWE-89"],
        "osv_ids": [],
        "fixed_versions": ["1.2.3"],
        "fix_prs": ["#42"],
        "fix_commits": ["abc1234"],
        "advisory_urls": ["https://nvd.nist.gov/vuln/detail/CVE-2024-1234"],
    },
    "comments": [
        {"id": "c0", "author": "alice", "timestamp": "2024-01-01T00:00:00Z",
         "body": "I found a bug in version 1.2.0. Is it fixed?", "role": "body"},
        {"id": "c1", "author": "bob", "timestamp": "2024-01-02T00:00:00Z",
         "body": "Fixed in 1.2.3 via PR #42 (CVE-2024-1234).", "role": "comment"},
    ],
    "human_note": "",
    "llm_confidence": 0.9,
}

MID_THREAD_ROW = {
    **SAMPLE_ROW,
    "question_comment_id": "c1",
    "answer_comment_id": "c2",
    "comments": [
        {"id": "c0", "author": "alice", "timestamp": "2024-01-01T00:00:00Z",
         "body": "Initial report.", "role": "body"},
        {"id": "c1", "author": "bob", "timestamp": "2024-01-01T12:00:00Z",
         "body": "Is this the same as the above issue?", "role": "comment"},
        {"id": "c2", "author": "maintainer", "timestamp": "2024-01-02T00:00:00Z",
         "body": "Yes, see CVE-2024-1234.", "role": "comment"},
    ],
}


def test_load_benchmark_valid(tmp_path):
    f = tmp_path / "bench.jsonl"
    f.write_text(json.dumps(SAMPLE_ROW) + "\n")
    rows = load_benchmark(f)
    assert len(rows) == 1
    assert rows[0]["id"] == "test/repo/issue/1"


def test_load_benchmark_malformed(tmp_path):
    f = tmp_path / "bench.jsonl"
    f.write_text("not json\n")
    with pytest.raises(ValueError, match="Malformed JSON"):
        load_benchmark(f)


def test_get_question_comment():
    c = get_question_comment(SAMPLE_ROW)
    assert c["id"] == "c0"
    assert c["author"] == "alice"


def test_get_answer_comment():
    c = get_answer_comment(SAMPLE_ROW)
    assert c["id"] == "c1"


def test_get_thread_before_answer_body_question():
    thread = get_thread_before_answer(SAMPLE_ROW)
    assert len(thread) == 1
    assert thread[0]["id"] == "c0"


def test_get_thread_before_answer_mid_thread():
    thread = get_thread_before_answer(MID_THREAD_ROW)
    assert len(thread) == 2
    assert thread[-1]["id"] == "c1"


def test_question_source_body():
    assert question_source(SAMPLE_ROW) == "issue_body"


def test_question_source_thread():
    assert question_source(MID_THREAD_ROW) == "thread_comment"


def test_sha256_text_deterministic():
    h1 = sha256_text("hello")
    h2 = sha256_text("hello")
    assert h1 == h2
    assert len(h1) == 64


def test_sha256_text_different():
    assert sha256_text("hello") != sha256_text("world")


def test_find_reporter_cited_identifiers_cve():
    text = "This relates to CVE-2024-1234 in semver."
    ids = find_reporter_cited_identifiers(text)
    assert "CVE-2024-1234" in ids


def test_find_reporter_cited_identifiers_ghsa():
    text = "See GHSA-abcd-efgh-ijkl for details."
    ids = find_reporter_cited_identifiers(text)
    assert any("GHSA" in i for i in ids)


def test_find_reporter_cited_identifiers_empty():
    text = "I have a question about the library."
    ids = find_reporter_cited_identifiers(text)
    assert ids == []


def test_find_hard_fact_leaks_detects_cve():
    draft = "This is fixed in CVE-2024-1234 via version 1.2.3."
    leaks = find_hard_fact_leaks(draft, SAMPLE_ROW["hard_facts"])
    assert any("CVE-2024-1234" in l for l in leaks)


def test_find_hard_fact_leaks_no_leak():
    draft = "Is this library affected by this type of vulnerability?"
    leaks = find_hard_fact_leaks(draft, SAMPLE_ROW["hard_facts"])
    assert leaks == []


def test_identifier_patterns_cve():
    pat = IDENTIFIER_PATTERNS["cve"]
    assert pat.search("CVE-2022-25883")
    assert pat.search("cve-2022-25883")
    assert not pat.search("CVE-22-123")  # too short year


def test_identifier_patterns_ghsa():
    pat = IDENTIFIER_PATTERNS["ghsa"]
    assert pat.search("GHSA-abcd-1234-efgh")
    assert not pat.search("GHSA-abc-1234-efgh")  # wrong segment length


def test_validate_benchmark_row_valid():
    validate_benchmark_row(SAMPLE_ROW)  # should not raise


def test_validate_benchmark_row_missing_field():
    bad = {k: v for k, v in SAMPLE_ROW.items() if k != "comments"}
    with pytest.raises(ValueError):
        validate_benchmark_row(bad)


def test_build_thread_text_excludes_answer():
    text = build_thread_text(SAMPLE_ROW)
    # Answer body should not appear
    assert "Fixed in 1.2.3" not in text
    # Question body should appear
    assert "I found a bug" in text


def test_infer_provider_openai():
    assert infer_provider("gpt-4o") == "openai"


def test_infer_provider_anthropic():
    assert infer_provider("anthropic/claude-sonnet-4-6") == "anthropic"


def test_infer_provider_ollama():
    assert infer_provider("ollama/qwen2.5:72b") == "ollama"
