"""Run monitoring routes: listing, detail, delete, transcript, live events."""

from __future__ import annotations

import json
import shutil
import time

from fastapi import APIRouter, HTTPException

from .shared import (
    ACTIVE_SECS,
    OUTPUT_DIR,
    RUN_NAME_RE,
    grade_files,
    grading_summary,
    grades_for,
    launch_meta_path,
    read_jsonl,
    totals,
)

router = APIRouter()


@router.get("/api/runs")
def runs():
    now = time.time()
    out = []
    for path in sorted(OUTPUT_DIR.glob("answers_*.jsonl")):
        name = path.stem.removeprefix("answers_")
        recs = read_jsonl(path)
        ok = [r for r in recs if not r.get("error")]
        gradings = [grading_summary(p) for p in grade_files(name)]
        default = gradings[0] if gradings else {}
        tool_groups: dict[str, int] = {}
        for r in ok:
            for grp, n in (r.get("tool_calls_by_group") or {}).items():
                tool_groups[grp] = tool_groups.get(grp, 0) + n
        last = recs[-1] if recs else {}
        mtime = path.stat().st_mtime
        out.append({
            "name": name,
            "model": last.get("model", "?"),
            "condition": last.get("condition", "?"),
            "n_done": len(ok),
            "n_errors": len(recs) - len(ok),
            "n_graded": default.get("n_graded", 0),
            "judge_model": default.get("judge_model"),
            "gradings": gradings,
            "outcomes": default.get("outcomes", {}),
            "n_hallucinated": default.get("n_hallucinated", 0),
            "n_flagged": default.get("n_flagged", 0),
            "tool_groups": tool_groups,
            "is_agent": str(last.get("condition", "")).startswith(
                ("snapshot_agent", "agent", "coding_agent_")
            ),
            "updated_secs_ago": int(now - mtime),
            "running": (now - mtime) < ACTIVE_SECS,
        })
    out.sort(key=lambda r: r["updated_secs_ago"])
    return {"runs": out, "totals": totals()}


@router.get("/api/runs/{name}")
def run_detail(name: str, tail: int = 50, judge: str | None = None):
    path = OUTPUT_DIR / f"answers_{name}.jsonl"
    if not path.exists():
        raise HTTPException(404, f"no run named {name}")
    grades, judge_slug = grades_for(name, judge)
    items = []
    for r in read_jsonl(path)[-tail:]:
        g = grades.get(r.get("qid"))
        legacy = (g or {}).get("judge") or {}
        items.append({
            "qid": r.get("qid"),
            "qid_slug": str(r.get("qid", "")).replace("/", "__"),
            "repo": r.get("repo"),
            "knowledge_type": r.get("knowledge_type"),
            "error": r.get("error"),
            "chars": len(r.get("response") or ""),
            "n_tool_calls": r.get("n_tool_calls"),
            "tool_calls_by_group": r.get("tool_calls_by_group"),
            "runtime_secs": r.get("runtime_secs"),
            "snapshot": r.get("snapshot"),
            "question": r.get("question") or "",
            "response": r.get("response") or "",
            "outcome": (g or {}).get("outcome"),
            "hallucinated": (g or {}).get("hallucinated"),
            "flags": (g or {}).get("flags"),
            "rubric_grades": (g or {}).get("rubric_grades"),
            "scores": (g or {}).get("scores"),
            "hallucinations": (
                (g or {}).get("hallucinations") or legacy.get("hallucinations")
            ),
            "claims": legacy.get("claims"),
            "hard_facts": (g or {}).get("hard_facts"),
        })
    items.reverse()
    return {"name": name, "items": items, "judge": judge_slug}


@router.delete("/api/runs/{name}")
def delete_run(name: str):
    """Delete a run's artifacts. Refuses while the run looks active."""
    if not RUN_NAME_RE.match(name):
        raise HTTPException(400, "invalid run name")
    answers = OUTPUT_DIR / f"answers_{name}.jsonl"
    if not answers.exists():
        raise HTTPException(404, f"no run named {name}")
    if (time.time() - answers.stat().st_mtime) < ACTIVE_SECS:
        raise HTTPException(
            409,
            f"run looks active (written within the last {ACTIVE_SECS}s)"
            " — stop it before deleting",
        )
    removed = []
    for p in (answers, launch_meta_path(name), *grade_files(name)):
        if p.exists():
            p.unlink()
            removed.append(p.name)
    tdir = OUTPUT_DIR / "transcripts" / name
    if tdir.is_dir():
        shutil.rmtree(tdir)
        removed.append(f"transcripts/{name}/")
    return {"ok": True, "removed": removed}


@router.get("/api/transcript/{name}/{qid_slug}")
def transcript(name: str, qid_slug: str):
    path = OUTPUT_DIR / "transcripts" / name / f"{qid_slug}.json"
    if not path.exists():
        raise HTTPException(404, "no transcript for this item")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/api/live/{name}/{qid_slug}")
def live(name: str, qid_slug: str, since: int = 0):
    """Live event stream for an in-flight item, polled by the UI."""
    if not RUN_NAME_RE.match(name):
        raise HTTPException(400, "invalid run name")
    live_path = OUTPUT_DIR / "transcripts" / name / f"{qid_slug}.live.jsonl"
    final_path = OUTPUT_DIR / "transcripts" / name / f"{qid_slug}.json"
    # tool_result events carry the verbatim tool output (the durable record the final
    # transcript is rebuilt from). The live timeline only needs `chars`, so drop the
    # payload here rather than shipping every tool result on every poll.
    events = [{k: v for k, v in e.items() if k != "result"}
              for e in read_jsonl(live_path)]
    done = (
        bool(events and events[-1].get("t") in ("done", "final", "final_forced"))
        or final_path.exists()
    )
    return {"events": events[since:], "total": len(events), "done": done}
