"""Tests for eval/generate.py — mock mode, resumability, output schema."""

import json
import tempfile
from pathlib import Path

import pytest

from eval.generate import _load_done_tuples, generate
from eval.data import sha256_text
from eval.config import SYSTEM_PROMPT


APPROVED_QUESTION = {
    "id": "test/repo/issue/1",
    "eval_question": "Is this library vulnerable to the reported issue, and what version fixes it?",
    "question_source": "issue_body",
    "reporter_cited_identifiers": [],
    "leak_flags": [],
    "needs_human_review": False,
    "normalizer_model": "gpt-4o",
    "approved": True,
}

UNAPPROVED_QUESTION = {
    **APPROVED_QUESTION,
    "id": "test/repo/issue/2",
    "approved": False,
}


def _write_questions(path: Path, rows: list[dict]) -> None:
    with open(path, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def test_mock_run_produces_output(tmp_path):
    questions_path = tmp_path / "eval_questions.jsonl"
    output_path = tmp_path / "answers_test.jsonl"
    _write_questions(questions_path, [APPROVED_QUESTION])

    generate(
        questions_path=questions_path,
        model_list=["gpt-4o"],
        output_path=output_path,
        n_samples=1,
        resume=False,
        mock=True,
        run_id="test",
    )

    assert output_path.exists()
    lines = output_path.read_text().strip().split("\n")
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["pair_id"] == "test/repo/issue/1"
    assert rec["model"] == "gpt-4o"
    assert rec["condition"] == "no_context"
    assert rec["response_text"] is not None
    assert rec["error"] is None
    assert rec["run_id"] == "test"
    assert rec["n_sample_index"] == 0


def test_mock_run_output_schema(tmp_path):
    questions_path = tmp_path / "eval_questions.jsonl"
    output_path = tmp_path / "answers_test.jsonl"
    _write_questions(questions_path, [APPROVED_QUESTION])

    generate(
        questions_path=questions_path,
        model_list=["gpt-4o"],
        output_path=output_path,
        n_samples=1,
        resume=False,
        mock=True,
        run_id="schema-test",
    )

    rec = json.loads(output_path.read_text().strip())
    required_fields = [
        "pair_id", "condition", "model", "provider", "eval_question_hash",
        "system_prompt_hash", "response_text", "usage", "cost_usd", "latency_s",
        "temperature", "n_sample_index", "timestamp", "git_rev", "run_id", "error",
    ]
    for field in required_fields:
        assert field in rec, f"Missing field: {field}"


def test_system_prompt_hash_consistent(tmp_path):
    questions_path = tmp_path / "eval_questions.jsonl"
    output_path = tmp_path / "answers_test.jsonl"
    _write_questions(questions_path, [APPROVED_QUESTION])

    generate(
        questions_path=questions_path,
        model_list=["gpt-4o"],
        output_path=output_path,
        n_samples=1,
        resume=False,
        mock=True,
        run_id="hash-test",
    )

    rec = json.loads(output_path.read_text().strip())
    assert rec["system_prompt_hash"] == sha256_text(SYSTEM_PROMPT)


def test_unapproved_questions_excluded(tmp_path):
    questions_path = tmp_path / "eval_questions.jsonl"
    output_path = tmp_path / "answers_test.jsonl"
    _write_questions(questions_path, [UNAPPROVED_QUESTION])

    with pytest.raises(SystemExit):
        generate(
            questions_path=questions_path,
            model_list=["gpt-4o"],
            output_path=output_path,
            n_samples=1,
            resume=False,
            mock=True,
            run_id="no-approved",
        )


def test_n_samples(tmp_path):
    questions_path = tmp_path / "eval_questions.jsonl"
    output_path = tmp_path / "answers_test.jsonl"
    _write_questions(questions_path, [APPROVED_QUESTION])

    generate(
        questions_path=questions_path,
        model_list=["gpt-4o"],
        output_path=output_path,
        n_samples=3,
        resume=False,
        mock=True,
        run_id="n3",
    )

    lines = output_path.read_text().strip().split("\n")
    assert len(lines) == 3
    indices = [json.loads(l)["n_sample_index"] for l in lines]
    assert sorted(indices) == [0, 1, 2]


def test_resume_skips_done(tmp_path):
    questions_path = tmp_path / "eval_questions.jsonl"
    output_path = tmp_path / "answers_test.jsonl"
    _write_questions(questions_path, [APPROVED_QUESTION])

    # First run
    generate(
        questions_path=questions_path,
        model_list=["gpt-4o"],
        output_path=output_path,
        n_samples=1,
        resume=False,
        mock=True,
        run_id="r1",
    )

    # Second run with resume — should not duplicate
    generate(
        questions_path=questions_path,
        model_list=["gpt-4o"],
        output_path=output_path,
        n_samples=1,
        resume=True,
        mock=True,
        run_id="r2",
    )

    lines = [l for l in output_path.read_text().strip().split("\n") if l]
    assert len(lines) == 1


def test_load_done_tuples_empty(tmp_path):
    path = tmp_path / "nonexistent.jsonl"
    done = _load_done_tuples(path)
    assert done == set()


def test_load_done_tuples_with_data(tmp_path):
    path = tmp_path / "answers.jsonl"
    rec = {"pair_id": "a/b/1", "model": "gpt-4o", "n_sample_index": 0, "other": "x"}
    path.write_text(json.dumps(rec) + "\n")
    done = _load_done_tuples(path)
    assert ("a/b/1", "gpt-4o", 0) in done


def test_multiple_models_mock(tmp_path):
    questions_path = tmp_path / "eval_questions.jsonl"
    output_path = tmp_path / "answers_test.jsonl"
    _write_questions(questions_path, [APPROVED_QUESTION])

    generate(
        questions_path=questions_path,
        model_list=["gpt-4o", "anthropic/claude-sonnet-4-6"],
        output_path=output_path,
        n_samples=1,
        resume=False,
        mock=True,
        run_id="multi",
    )

    lines = [l for l in output_path.read_text().strip().split("\n") if l]
    assert len(lines) == 2
    models_seen = {json.loads(l)["model"] for l in lines}
    assert models_seen == {"gpt-4o", "anthropic/claude-sonnet-4-6"}
