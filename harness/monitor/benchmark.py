"""Benchmark browse routes: QA pair list and item detail."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .shared import benchmark_source, read_jsonl

router = APIRouter()

_HARD_ID_FIELDS = ("cve_ids", "ghsa_ids", "cwe_ids", "osv_ids")


def _nonempty_hard_facts(hf: dict) -> dict:
    return {k: v for k, v in (hf or {}).items() if v}


def qa_slug(repo: str, number, qid: str) -> str:
    """Readable URL-safe id: ``owner_repo_<number>_q<k>``."""
    k = str(qid).split("#")[-1] if qid else ""
    return f"{str(repo or '').replace('/', '_')}_{number}_q{k}"


def _slug_to_qid() -> dict[str, str]:
    out = {}
    for t in read_jsonl(benchmark_source()):
        if t.get("error"):
            continue
        for qa in t.get("qa_pairs") or []:
            qid = qa.get("qid")
            if qid:
                out[qa_slug(t.get("repo"), t.get("number"), qid)] = qid
    return out


@router.get("/api/benchmark")
def benchmark_list():
    """All QA pairs with list-view fields and filter facets."""
    items, repos, artifacts, kinds = [], set(), set(), set()
    for t in read_jsonl(benchmark_source()):
        if t.get("error"):
            continue
        hf = _nonempty_hard_facts(t.get("hard_facts") or {})
        for qa in t.get("qa_pairs") or []:
            arts = t.get("artifacts_needed") or []
            repos.add(t.get("repo"))
            artifacts.update(arts)
            kinds.add(qa.get("knowledge_type"))
            items.append({
                "n_rubric": len(qa.get("rubric") or []),
                "qid": qa.get("qid"),
                "slug": qa_slug(t.get("repo"), t.get("number"), qa.get("qid")),
                "repo": t.get("repo"),
                "number": t.get("number"),
                "url": t.get("url"),
                "title": t.get("title"),
                "state": t.get("state"),
                "knowledge_type": qa.get("knowledge_type"),
                "security_topic": t.get("security_topic"),
                "qa_summary": t.get("qa_summary"),
                "artifacts_needed": arts,
                "answerer_role": t.get("answerer_role"),
                "labels": t.get("labels") or [],
                "hard_facts": hf,
                "has_hard_id": any(
                    t.get("hard_facts", {}).get(f) for f in _HARD_ID_FIELDS
                ),
                "n_comments": len(t.get("comments") or []),
                "question": qa.get("question") or "",
            })
    return {
        "count": len(items),
        "items": items,
        "facets": {
            "repos": sorted(r for r in repos if r),
            "artifacts": sorted(a for a in artifacts if a),
            "knowledge_types": sorted(k for k in kinds if k),
        },
    }


@router.get("/api/benchmark/item")
def benchmark_item(qid: str = None, slug: str = None):
    """Full detail for one QA pair, by canonical qid or readable slug."""
    if not qid and slug:
        qid = _slug_to_qid().get(slug)
    if not qid:
        raise HTTPException(404, f"no QA pair for slug {slug!r}")
    for t in read_jsonl(benchmark_source()):
        if t.get("error"):
            continue
        for qa in t.get("qa_pairs") or []:
            if qa.get("qid") != qid:
                continue
            return {
                "slug": qa_slug(t.get("repo"), t.get("number"), qid),
                "rubric": qa.get("rubric") or [],
                "acceptable_alternatives": qa.get("acceptable_alternatives") or [],
                "rubric_note": qa.get("rubric_note") or "",
                "qid": qid,
                "repo": t.get("repo"),
                "number": t.get("number"),
                "url": t.get("url"),
                "title": t.get("title"),
                "state": t.get("state"),
                "created_at": t.get("created_at"),
                "closed_at": t.get("closed_at"),
                "reporter": t.get("reporter"),
                "labels": t.get("labels") or [],
                "security_topic": t.get("security_topic"),
                "qa_summary": t.get("qa_summary"),
                "question_author": t.get("question_author"),
                "answer_author": t.get("answer_author"),
                "answerer_role": t.get("answerer_role"),
                "question_comment_id": t.get("question_comment_id"),
                "answer_comment_id": t.get("answer_comment_id"),
                "artifacts_needed": t.get("artifacts_needed") or [],
                "hard_facts": _nonempty_hard_facts(t.get("hard_facts") or {}),
                "llm_confidence": t.get("llm_confidence"),
                "human_note": t.get("human_note"),
                "review_note": t.get("review_note"),
                "leak_flags": t.get("leak_flags") or [],
                "question": qa.get("question") or "",
                "answer": qa.get("answer") or "",
                "knowledge_type": qa.get("knowledge_type"),
                "grounding_sources": qa.get("grounding_sources"),
                "answer_grounded_in": qa.get("answer_grounded_in"),
                "answer_in_thread_refs": t.get("answer_in_thread_refs") or [],
                "comments": t.get("comments") or [],
            }
    raise HTTPException(404, f"no QA pair with qid {qid}")
