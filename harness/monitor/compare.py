"""Compare route: side-by-side predictions across runs."""

from __future__ import annotations

from fastapi import APIRouter

from .shared import OUTPUT_DIR, benchmark_source, grades_for, read_jsonl

router = APIRouter()


def _gold_map() -> dict[str, dict]:
    gold: dict[str, dict] = {}
    for thread in read_jsonl(benchmark_source()):
        if thread.get("error"):
            continue
        for qa in thread.get("qa_pairs") or []:
            qid = qa.get("qid")
            if not qid:
                continue
            gold[qid] = {
                "thread_id": thread.get("thread_id") or thread.get("id"),
                "repo": thread.get("repo"),
                "url": thread.get("url"),
                "title": thread.get("title"),
                "knowledge_type": qa.get("knowledge_type"),
                "question": qa.get("question"),
                "gold_answer": qa.get("answer"),
                "grounding_sources": qa.get("grounding_sources"),
                "hard_facts": thread.get("hard_facts"),
                "approved": bool(thread.get("approved", True)),
            }
    return gold


def _run_index(
    name: str, judge: str | None = None
) -> tuple[dict[str, dict], dict[str, dict]] | None:
    apath = OUTPUT_DIR / f"answers_{name}.jsonl"
    if not apath.exists():
        return None
    answers = {r["qid"]: r for r in read_jsonl(apath) if r.get("qid")}
    grades, _ = grades_for(name, judge)
    return answers, grades


@router.get("/api/compare")
def compare(runs: str = ""):
    """Side-by-side predictions for the given columns, joined per question.

    Each column is `run` or `run@judge-slug`; the same run can appear under
    several judges for cross-judge comparison."""
    specs = [n for n in (runs.split(",") if runs else []) if n]
    indexed: dict[str, tuple[dict, dict, str]] = {}
    meta = []
    for spec in specs:
        run, _, judge = spec.partition("@")
        idx = _run_index(run, judge or None)
        if idx is None:
            continue
        answers, grades = idx
        indexed[spec] = (answers, grades, run)
        sample = next(iter(answers.values()), {})
        judges = {
            g.get("judge_model")
            for g in grades.values()
            if g.get("judge_model")
        }
        meta.append({
            "name": spec,
            "run": run,
            "model": sample.get("model", "?"),
            "condition": sample.get("condition", "?"),
            "judge_model": (
                "mixed" if len(judges) > 1
                else next(iter(judges)) if judges else None
            ),
            "is_agent": str(sample.get("condition", "")).startswith(
                ("snapshot_agent", "agent", "external_")
            ),
            "n_done": len(answers),
            "n_graded": len(grades),
        })

    gold = _gold_map()
    qids: list[str] = []
    seen: set[str] = set()
    for qid in gold:
        if any(qid in answers for answers, _, _ in indexed.values()):
            qids.append(qid)
            seen.add(qid)
    for answers, _, _ in indexed.values():
        for qid in answers:
            if qid not in seen:
                qids.append(qid)
                seen.add(qid)

    rows = []
    for qid in qids:
        g = gold.get(qid, {})
        cells = {}
        for spec, (answers, grades, run) in indexed.items():
            a = answers.get(qid)
            if a is None:
                cells[spec] = None
                continue
            gr = grades.get(qid) or {}
            legacy = gr.get("judge") or {}
            slug = str(qid).replace("/", "__")
            cells[spec] = {
                "response": a.get("response") or "",
                "error": a.get("error"),
                "runtime_secs": a.get("runtime_secs"),
                "n_tool_calls": a.get("n_tool_calls"),
                "tool_calls_by_group": a.get("tool_calls_by_group"),
                "usage": a.get("usage"),
                "outcome": gr.get("outcome"),
                "hallucinated": gr.get("hallucinated"),
                "flags": gr.get("flags"),
                "hard_facts": gr.get("hard_facts"),
                "rubric_grades": gr.get("rubric_grades"),
                "scores": gr.get("scores"),
                "hallucinations": (
                    gr.get("hallucinations") or legacy.get("hallucinations")
                ),
                "claims": legacy.get("claims"),
                "graded": bool(gr),
                "has_transcript": (
                    OUTPUT_DIR / "transcripts" / run / f"{slug}.json"
                ).exists(),
            }
        rows.append({
            "qid": qid,
            "qid_slug": str(qid).replace("/", "__"),
            "repo": g.get("repo") or (
                qid.rsplit("/issue", 1)[0] if qid else None
            ),
            "url": g.get("url"),
            "title": g.get("title"),
            "knowledge_type": g.get("knowledge_type"),
            "question": g.get("question"),
            "gold_answer": g.get("gold_answer"),
            "grounding_sources": g.get("grounding_sources"),
            "hard_facts": g.get("hard_facts"),
            "in_corpus": qid in gold,
            "cells": cells,
        })
    return {"runs": meta, "rows": rows}
