"""
SecDevQA harness — web UI: launch evaluation runs and monitor them live.

A standalone FastAPI app (port 8766) over harness/output/, distinct from the
benchmark/review UI (review_ui/app.py, port 8765). Three halves:

  * Launcher — pick a system (bare LLM / built-in snapshot agent / claude-code /
    opencode), model, artifact-group context selection, limit, and optional
    auto-grading; the server spawns the corresponding `python -m harness ...` CLI as a
    subprocess (logged to harness/output/logs/), so everything the UI does is exactly
    reproducible from the shell.
  * Monitor — read-only polling over the answers_*/grades_* JSONL files and transcripts;
    tolerant of half-written lines, needs no coordination with runs.
  * Compare — per-question matrix across selected runs (GET /api/compare), joining each
    run's answer + grade with the gold maintainer answer so predictions can be browsed
    side by side and filtered by knowledge type, outcome, repo, or disagreement.

Usage:
  python -m harness ui              # http://localhost:8766
  python -m harness ui --port 9000
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from harness.agent import condition_name as agent_condition_name
from harness.answer import slugify
from harness.external import AGENTS as EXTERNAL_AGENTS
from harness.grade import DEFAULT_JUDGE as GRADE_DEFAULT_JUDGE
from harness.tools import ALL_GROUPS

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "harness" / "output"
LOGS_DIR = OUTPUT_DIR / "logs"
PAIRS_FILE = ROOT / "dataset" / "security_benchmark_final.jsonl"
# The released benchmark: accepted-rubric qa_pairs only, rubric embedded
# (dataset/build_release.py). The browse page serves this when present; the eval
# corpus (grading/compare) still reads the full PAIRS_FILE.
RELEASE_FILE = ROOT / "dataset" / "security_benchmark_release.jsonl"
MODELS_CONFIG = Path(__file__).parent / "models.json"   # launcher dropdown suggestions
UI_DIR = Path(__file__).parent / "ui"          # Vite project (source)
DIST_DIR = UI_DIR / "dist"                      # built bundle served in production
HTML_FILE = DIST_DIR / "index.html"

BUILD_HINT = (
    "<html><body style='font-family:system-ui;background:#0b0e14;color:#e6eaf2;"
    "padding:60px;line-height:1.6'><h2>Harness UI not built</h2><p>The React app "
    "under <code>harness/ui/</code> hasn't been built yet. From that directory run:"
    "</p><pre style='background:#19202e;padding:14px;border-radius:8px'>"
    "npm install\nnpm run build</pre><p>then reload. For live development instead, "
    "run <code>npm run dev</code> (proxies the API to this server on :8766).</p>"
    "</body></html>"
)

DEFAULT_PORT = 8766
ACTIVE_SECS = 90       # answers file modified within this window → run shown as live

app = FastAPI(title="SecDevQA — evaluation harness")

# Launched processes, by id. The registry is in-memory by design — runs are plain CLI
# processes and survive a UI restart; only their stop-buttons are lost.
PROCS: dict[str, dict] = {}


def read_jsonl(path: Path) -> list[dict]:
    """Tolerant JSONL reader: skips blank and half-written lines (live runs)."""
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError:
        pass
    return out


def benchmark_source() -> Path:
    """The released benchmark when it has been built, else the full corpus."""
    return RELEASE_FILE if RELEASE_FILE.exists() else PAIRS_FILE


# --- Grades: one file per (run × judge) ------------------------------------
# grades_<run>__judge-<slug>.jsonl, plus a legacy grades_<run>.jsonl from before
# per-judge files existed. So a run can carry several gradings (one per judge).
_JUDGE_SLUG_RE = re.compile(r"__judge-(.+)\.jsonl$")


def grade_files(name: str) -> list[Path]:
    """All grades files for a run, newest first."""
    fs = list(OUTPUT_DIR.glob(f"grades_{name}__judge-*.jsonl"))
    legacy = OUTPUT_DIR / f"grades_{name}.jsonl"
    if legacy.exists():
        fs.append(legacy)
    return sorted(fs, key=lambda p: p.stat().st_mtime, reverse=True)


def _slug_of(path: Path) -> str | None:
    m = _JUDGE_SLUG_RE.search(path.name)
    return m.group(1) if m else None


def grading_summary(path: Path) -> dict:
    outcomes: dict[str, int] = {}
    judges: set[str] = set()
    n = nh = nf = 0
    for g in read_jsonl(path):
        if g.get("error"):
            continue
        n += 1
        outcomes[g.get("outcome", "?")] = outcomes.get(g.get("outcome", "?"), 0) + 1
        nh += 1 if g.get("hallucinated") else 0
        nf += 1 if g.get("flags") else 0
        if g.get("judge_model"):
            judges.add(g["judge_model"])
    judge = "mixed" if len(judges) > 1 else (next(iter(judges)) if judges else None)
    return {"slug": _slug_of(path), "judge_model": judge, "n_graded": n,
            "outcomes": outcomes, "n_hallucinated": nh, "n_flagged": nf}


def grades_for(name: str, judge: str | None = None) -> tuple[dict[str, dict], str | None]:
    """(qid → grade record, judge-slug) for one run, choosing the requested judge
    slug or the most recent grading."""
    fs = grade_files(name)
    if not fs:
        return {}, None
    chosen = next((p for p in fs if judge and _slug_of(p) == judge), fs[0])
    grades = {g["qid"]: g for g in read_jsonl(chosen)
              if g.get("qid") and not g.get("error")}
    return grades, _slug_of(chosen)


# Minimal fallback if models.json is missing or unreadable — the real lists live there.
_MODELS_FALLBACK = {
    "model_suggestions": ["openai/gpt-5.4-mini", "anthropic/claude-sonnet-4-6",
                          "ollama/gemma4:31b"],
    "judge_suggestions": ["openai/gpt-5.4", "anthropic/claude-opus-4-8"],
}


def model_config() -> dict:
    """Launcher dropdown suggestions, read live from models.json (so edits need no
    restart). Falls back to a small built-in list if the file is missing/broken."""
    try:
        cfg = json.loads(MODELS_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(_MODELS_FALLBACK)
    return {
        "model_suggestions": cfg.get("model_suggestions") or _MODELS_FALLBACK["model_suggestions"],
        "judge_suggestions": cfg.get("judge_suggestions") or _MODELS_FALLBACK["judge_suggestions"],
    }


def totals() -> dict:
    # Reflect the released benchmark the page browses (accepted-rubric qa_pairs only),
    # not the full corpus. Missing `approved` counts as approved (release is final).
    threads = read_jsonl(benchmark_source())
    return {
        "items_total": sum(len(t.get("qa_pairs") or [])
                           for t in threads if not t.get("error")),
        "items_approved": sum(len(t.get("qa_pairs") or [])
                              for t in threads
                              if t.get("approved", True) and not t.get("error")),
    }


# ---------------------------------------------------------------------------
# Monitoring APIs
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def page():
    if not HTML_FILE.exists():
        return HTMLResponse(BUILD_HINT, status_code=503)
    return HTMLResponse(HTML_FILE.read_text(encoding="utf-8"))


# The built Vite bundle references its assets under /static/ (see ui/vite.config.js).
if DIST_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(DIST_DIR)), name="static")


@app.get("/api/runs")
def runs():
    now = time.time()
    out = []
    for path in sorted(OUTPUT_DIR.glob("answers_*.jsonl")):
        name = path.stem.removeprefix("answers_")
        recs = read_jsonl(path)
        ok = [r for r in recs if not r.get("error")]
        # Each run may have several gradings (one per judge). The default shown on the
        # card is the most recent; the full list drives the per-run judge selector.
        gradings = [grading_summary(p) for p in grade_files(name)]
        default = gradings[0] if gradings else {}
        outcomes = default.get("outcomes", {})
        n_graded = default.get("n_graded", 0)
        n_halluc = default.get("n_hallucinated", 0)
        n_flags = default.get("n_flagged", 0)
        judge_model = default.get("judge_model")
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
            "n_graded": n_graded,
            "judge_model": judge_model,
            "gradings": gradings,
            "outcomes": outcomes,
            "n_hallucinated": n_halluc,
            "n_flagged": n_flags,
            "tool_groups": tool_groups,
            "is_agent": str(last.get("condition", "")).startswith(
                ("snapshot_agent", "agent", "external_")),
            "updated_secs_ago": int(now - mtime),
            "running": (now - mtime) < ACTIVE_SECS,
        })
    out.sort(key=lambda r: r["updated_secs_ago"])
    return {"runs": out, "totals": totals()}


@app.get("/api/runs/{name}")
def run_detail(name: str, tail: int = 50, judge: str | None = None):
    path = OUTPUT_DIR / f"answers_{name}.jsonl"
    if not path.exists():
        raise HTTPException(404, f"no run named {name}")
    grades, judge_slug = grades_for(name, judge)
    items = []
    for r in read_jsonl(path)[-tail:]:
        g = grades.get(r.get("qid"))
        legacy = (g or {}).get("judge") or {}   # legacy claim-based grades
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
            "hallucinations": (g or {}).get("hallucinations") or legacy.get("hallucinations"),
            "claims": legacy.get("claims"),   # legacy fallback
            "hard_facts": (g or {}).get("hard_facts"),
        })
    items.reverse()  # newest first
    return {"name": name, "items": items, "judge": judge_slug}


# Run names are produced by slugify() + condition_name(): word chars, dot, dash only.
# Validate against that charset so a path param can never escape OUTPUT_DIR.
_RUN_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@app.delete("/api/runs/{name}")
def delete_run(name: str):
    """Delete a run's artifacts: answers_<name>.jsonl, grades_<name>.jsonl, and
    transcripts/<name>/. Refuses while the run looks active (recently written) so we
    never race a live writer — stop it first."""
    if not _RUN_NAME_RE.match(name):
        raise HTTPException(400, "invalid run name")
    answers = OUTPUT_DIR / f"answers_{name}.jsonl"
    if not answers.exists():
        raise HTTPException(404, f"no run named {name}")
    if (time.time() - answers.stat().st_mtime) < ACTIVE_SECS:
        raise HTTPException(409, "run looks active (written within the last "
                                 f"{ACTIVE_SECS}s) — stop it before deleting")
    removed = []
    for p in (answers, *grade_files(name)):   # all per-judge gradings + legacy
        if p.exists():
            p.unlink()
            removed.append(p.name)
    tdir = OUTPUT_DIR / "transcripts" / name
    if tdir.is_dir():
        shutil.rmtree(tdir)
        removed.append(f"transcripts/{name}/")
    return {"ok": True, "removed": removed}


@app.get("/api/transcript/{name}/{qid_slug}")
def transcript(name: str, qid_slug: str):
    path = OUTPUT_DIR / "transcripts" / name / f"{qid_slug}.json"
    if not path.exists():
        raise HTTPException(404, "no transcript for this item")
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Benchmark API — browse the released QA pairs (security_benchmark_final.jsonl)
# ---------------------------------------------------------------------------

# Hard-fact fields that count as an externally-verifiable identifier.
_HARD_ID_FIELDS = ("cve_ids", "ghsa_ids", "cwe_ids", "osv_ids")


def _nonempty_hard_facts(hf: dict) -> dict:
    return {k: v for k, v in (hf or {}).items() if v}


def qa_slug(repo: str, number, qid: str) -> str:
    """A readable, URL-safe id for one QA pair: ``owner_repo_<number>_q<k>``
    (e.g. axios/axios/issue/6821#1 → axios_axios_6821_q1). Built from structured
    fields, so the inverse is an unambiguous lookup, not string parsing."""
    k = str(qid).split("#")[-1] if qid else ""
    return f"{str(repo or '').replace('/', '_')}_{number}_q{k}"


def _slug_to_qid() -> dict[str, str]:
    """slug → canonical qid, scanned from the benchmark the page browses."""
    out = {}
    for t in read_jsonl(benchmark_source()):
        if t.get("error"):
            continue
        for qa in t.get("qa_pairs") or []:
            qid = qa.get("qid")
            if qid:
                out[qa_slug(t.get("repo"), t.get("number"), qid)] = qid
    return out


@app.get("/api/benchmark")
def benchmark_list():
    """All QA pairs with the fields the list view needs, plus filter facets."""
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
                "has_hard_id": any(t.get("hard_facts", {}).get(f) for f in _HARD_ID_FIELDS),
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


@app.get("/api/benchmark/item")
def benchmark_item(qid: str = None, slug: str = None):
    """Full detail for one QA pair, addressed by canonical qid or readable slug
    (owner_repo_<number>_q<k>)."""
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
                "repo": t.get("repo"), "number": t.get("number"), "url": t.get("url"),
                "title": t.get("title"), "state": t.get("state"),
                "created_at": t.get("created_at"), "closed_at": t.get("closed_at"),
                "reporter": t.get("reporter"), "labels": t.get("labels") or [],
                "security_topic": t.get("security_topic"), "qa_summary": t.get("qa_summary"),
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
                # qa-pair fields
                "question": qa.get("question") or "",
                "answer": qa.get("answer") or "",
                "knowledge_type": qa.get("knowledge_type"),
                "grounding_sources": qa.get("grounding_sources"),
                "answer_grounded_in": qa.get("answer_grounded_in"),
                "answer_in_thread_refs": t.get("answer_in_thread_refs") or [],
                "comments": t.get("comments") or [],
            }
    raise HTTPException(404, f"no QA pair with qid {qid}")


# ---------------------------------------------------------------------------
# Comparison API — predictions across runs, side by side
# ---------------------------------------------------------------------------

def _gold_map() -> dict[str, dict]:
    """qid → reference question/answer/hard-facts, from the eval corpus."""
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


def _run_index(name: str, judge: str | None = None) -> tuple[dict[str, dict], dict[str, dict]] | None:
    """(answers-by-qid, grades-by-qid) for a run, or None if it doesn't exist.
    Uses the requested judge's grading, else the most recent."""
    apath = OUTPUT_DIR / f"answers_{name}.jsonl"
    if not apath.exists():
        return None
    answers = {r["qid"]: r for r in read_jsonl(apath) if r.get("qid")}
    grades, _ = grades_for(name, judge)
    return answers, grades


@app.get("/api/compare")
def compare(runs: str = ""):
    """Side-by-side predictions for the given columns, joined per question.

    Each column is a spec `run` or `run@judge-slug`: the same run can appear under
    several judges (one column each) so gradings by different LLM judges of the same
    answers are comparable side by side. Includes gold answer and per-column grading."""
    specs = [n for n in (runs.split(",") if runs else []) if n]
    indexed: dict[str, tuple[dict, dict, str]] = {}   # spec -> (answers, grades, bare run)
    meta = []
    for spec in specs:
        run, _, judge = spec.partition("@")
        idx = _run_index(run, judge or None)
        if idx is None:
            continue
        answers, grades = idx
        indexed[spec] = (answers, grades, run)
        sample = next(iter(answers.values()), {})
        judges = {g.get("judge_model") for g in grades.values() if g.get("judge_model")}
        meta.append({
            "name": spec,
            "run": run,
            "model": sample.get("model", "?"),
            "condition": sample.get("condition", "?"),
            "judge_model": ("mixed" if len(judges) > 1
                            else next(iter(judges)) if judges else None),
            "is_agent": str(sample.get("condition", "")).startswith(
                ("snapshot_agent", "agent", "external_")),
            "n_done": len(answers),
            "n_graded": len(grades),
        })

    gold = _gold_map()
    # Row order: every qid any selected run answered, gold-known first then extras.
    qids: list[str] = []
    seen = set()
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
            judge = gr.get("judge") or {}   # legacy claim-based grades
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
                "hallucinations": gr.get("hallucinations") or judge.get("hallucinations"),
                "claims": judge.get("claims"),   # legacy fallback
                "graded": bool(gr),
                "has_transcript": (OUTPUT_DIR / "transcripts" / run
                                   / f"{slug}.json").exists(),
            }
        rows.append({
            "qid": qid,
            "qid_slug": str(qid).replace("/", "__"),
            "repo": g.get("repo") or (qid.rsplit("/issue", 1)[0] if qid else None),
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


# ---------------------------------------------------------------------------
# Launcher APIs
# ---------------------------------------------------------------------------

@app.get("/api/options")
def options():
    """What the launch form can offer."""
    return {
        "systems": [
            {"id": "llm", "label": "Bare LLM (no_context)", "needs_model": True,
             "has_groups": False, "available": True},
            {"id": "agent", "label": "Built-in snapshot agent (typed tools)",
             "needs_model": True, "has_groups": True, "available": True},
            *[{"id": a, "label": f"External agent: {a}", "needs_model": False,
               "has_groups": False,
               "available": shutil.which(spec["cmd"][0]) is not None}
              for a, spec in EXTERNAL_AGENTS.items()],
        ],
        "groups": list(ALL_GROUPS),
        # LiteLLM model/judge suggestions, grouped by provider in the UI. From
        # models.json; any custom <provider>/<model> id can still be typed.
        **model_config(),
        "totals": totals(),
    }


class LaunchBody(BaseModel):
    system: str                       # llm | agent | claude-code | opencode
    model: str | None = None
    groups: list[str] | None = None   # built-in agent only; None/all → full snapshot
    limit: int | None = None
    include_unapproved: bool = False
    force: bool = False
    max_steps: int | None = None
    grade_after: bool = False
    judge: str | None = None


def _expected_run_name(body: LaunchBody) -> str:
    if body.system == "llm":
        return f"{slugify(body.model)}_no_context"
    if body.system == "agent":
        groups = set(body.groups) if body.groups else set(ALL_GROUPS)
        return f"{slugify(body.model)}_{agent_condition_name(groups)}"
    cond = f"external_{body.system.replace('-', '_')}"
    return f"{slugify(body.model) + '_' if body.model else ''}{cond}"


def _build_cmd(body: LaunchBody) -> tuple[list[str], str]:
    py = sys.executable
    common: list[str] = []
    if body.limit:
        common += ["--limit", str(body.limit)]
    if body.include_unapproved:
        common += ["--include-unapproved"]
    if body.force:
        common += ["--force"]

    if body.system == "llm":
        if not body.model:
            raise HTTPException(400, "model is required for the bare-LLM system")
        cmd = [py, "-m", "harness", "answer", "--model", body.model,
               "--condition", "no_context", *common]
    elif body.system == "agent":
        if not body.model:
            raise HTTPException(400, "model is required for the built-in agent")
        groups = set(body.groups) if body.groups else set(ALL_GROUPS)
        bad = groups - set(ALL_GROUPS)
        if bad:
            raise HTTPException(400, f"unknown groups: {sorted(bad)}")
        if not groups:
            raise HTTPException(400, "select at least one artifact group")
        cmd = [py, "-m", "harness", "agent", "--model", body.model, *common]
        if groups != set(ALL_GROUPS):
            cmd += ["--groups", ",".join(sorted(groups))]
        if body.max_steps:
            cmd += ["--max-steps", str(body.max_steps)]
    elif body.system in EXTERNAL_AGENTS:
        cmd = [py, "-m", "harness", "external", "--agent", body.system, *common]
        if body.model:
            cmd += ["--model", body.model]
    else:
        raise HTTPException(400, f"unknown system: {body.system}")

    run_name = _expected_run_name(body)
    shell = " ".join(shlex.quote(c) for c in cmd)
    if body.grade_after:
        answers = OUTPUT_DIR / f"answers_{run_name}.jsonl"
        gcmd = [py, "-m", "harness", "grade", "--answers", str(answers)]
        if body.judge:
            gcmd += ["--judge", body.judge]
        if body.force:                       # re-grade when the run is forced
            gcmd += ["--force"]
        shell += " && " + " ".join(shlex.quote(c) for c in gcmd)
    return ["bash", "-c", shell], run_name


def _spawn(cmd: list[str], run_name: str, display: str,
           answers_path: Path | None, grades_path: Path | None) -> str:
    """Start a tracked subprocess, capturing its output to a log. `answers_path` /
    `grades_path` are the output files whose line counts drive the answering / grading
    progress bars (a grade-after run writes both, in sequence)."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    proc_id = f"{ts}_{run_name}"
    log_path = LOGS_DIR / f"{proc_id}.log"
    log_fh = open(log_path, "w", encoding="utf-8")
    log_fh.write(f"$ {display}\n\n")
    log_fh.flush()
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log_fh, stderr=subprocess.STDOUT,
                            start_new_session=True)
    PROCS[proc_id] = {"proc": proc, "run_name": run_name, "cmd": display,
                      "log": str(log_path), "started": ts,
                      "answers_path": str(answers_path) if answers_path else None,
                      "grades_path": str(grades_path) if grades_path else None}
    return proc_id


@app.post("/api/launch")
def launch(body: LaunchBody):
    cmd, run_name = _build_cmd(body)
    display = cmd[-1]   # the bash -c shell string
    answers = OUTPUT_DIR / f"answers_{run_name}.jsonl"
    jslug = slugify(body.judge or GRADE_DEFAULT_JUDGE)
    grades = OUTPUT_DIR / f"grades_{run_name}__judge-{jslug}.jsonl"   # written iff grade_after
    proc_id = _spawn(cmd, run_name, display, answers, grades if body.grade_after else None)
    return {"ok": True, "proc_id": proc_id, "run_name": run_name, "cmd": display}


class GradeBody(BaseModel):
    judge: str | None = None
    force: bool = False


@app.post("/api/runs/{name}/grade")
def grade_run(name: str, body: GradeBody):
    """Grade (or re-grade) an existing run's answers, as a tracked process."""
    if not _RUN_NAME_RE.match(name):
        raise HTTPException(400, "bad run name")
    answers = OUTPUT_DIR / f"answers_{name}.jsonl"
    if not answers.exists():
        raise HTTPException(404, f"no answers for run {name}")
    gcmd = [sys.executable, "-m", "harness", "grade", "--answers", str(answers)]
    if body.judge:
        gcmd += ["--judge", body.judge]
    if body.force:
        gcmd += ["--force"]
    display = " ".join(shlex.quote(c) for c in gcmd)
    # answers already exists (the full input → the total); the per-judge grades file grows live.
    jslug = slugify(body.judge or GRADE_DEFAULT_JUDGE)
    grades = OUTPUT_DIR / f"grades_{name}__judge-{jslug}.jsonl"
    proc_id = _spawn(gcmd, f"{name}_grade", display, answers, grades)
    return {"ok": True, "proc_id": proc_id, "run_name": f"{name}_grade", "cmd": display}


# Stage progress lines look like "[12/50] owner/repo/issue/3#1 ...". The last match
# in the log tells us which item is in flight and how far along the run is.
_PROGRESS_RE = re.compile(r"\[(\d+)/(\d+)\]\s+(\S+)")


def _count_lines(path: str | None) -> int:
    try:
        if path and Path(path).exists():
            return sum(1 for ln in Path(path).read_text(
                encoding="utf-8", errors="replace").splitlines() if ln.strip())
    except OSError:
        pass
    return 0


def _proc_progress(info: dict, tail: str, running: bool) -> dict:
    matches = _PROGRESS_RE.findall(tail)
    idx = total = None
    current_qid = None
    if matches:
        idx, total, current_qid = matches[-1]
        idx, total = int(idx), int(total)
    answered = _count_lines(info.get("answers_path"))
    graded = _count_lines(info.get("grades_path"))
    has_grading = info.get("grades_path") is not None
    # The launcher chains "answer && grade"; the grade stage prints a "Judge:" banner.
    if not running:
        phase = "done"
    elif "Judge:" in tail and "\nGraded:" not in tail:
        phase = "grading"
    else:
        phase = "answering"
    # The live bar tracks whichever stage is in flight.
    live_done = graded if phase == "grading" else answered
    return {"current_qid": current_qid, "idx": idx, "total": total,
            "answered": answered, "graded": graded, "has_grading": has_grading,
            "live_done": live_done, "phase": phase}


@app.get("/api/procs")
def procs():
    out = []
    for pid, info in sorted(PROCS.items(), reverse=True):
        p = info["proc"]
        rc = p.poll()
        tail = ""
        try:
            tail = Path(info["log"]).read_text(
                encoding="utf-8", errors="replace")[-4000:]
        except OSError:
            pass
        out.append({"proc_id": pid, "run_name": info["run_name"],
                    "cmd": info["cmd"], "started": info["started"],
                    "running": rc is None, "returncode": rc, "log_tail": tail,
                    **_proc_progress(info, tail, rc is None)})
    return {"procs": out}


@app.post("/api/procs/{proc_id}/stop")
def stop(proc_id: str):
    info = PROCS.get(proc_id)
    if not info:
        raise HTTPException(404, "unknown process (server restarted? "
                                 "stop it from the shell)")
    p = info["proc"]
    if p.poll() is None:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
    return {"ok": True, "returncode": p.poll()}


@app.delete("/api/procs/{proc_id}")
def remove_proc(proc_id: str):
    """Drop a finished process from the list (and delete its captured log)."""
    info = PROCS.get(proc_id)
    if not info:
        raise HTTPException(404, "unknown process")
    if info["proc"].poll() is None:
        raise HTTPException(409, "process still running — stop it first")
    try:
        Path(info["log"]).unlink(missing_ok=True)
    except OSError:
        pass
    PROCS.pop(proc_id, None)
    return {"ok": True}


# The UI polls these endpoints on a timer to stay live (runs/procs ~3s, run detail
# ~4s, compare ~5s). That's one access-log line per poll per open tab — pure noise.
# Drop the successful polling requests from uvicorn's access log; keep launches,
# errors, asset loads, and anything non-2xx so real events stay visible.
_QUIET_POLL_PATHS = ("/api/runs", "/api/procs", "/api/compare", "/api/transcript")


class _QuietPollingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # uvicorn access records carry args = (client, method, path, http_ver, status).
        args = record.args
        if isinstance(args, tuple) and len(args) >= 5:
            path, status = str(args[2]), args[4]
            if isinstance(status, int) and 200 <= status < 400 \
                    and path.startswith(_QUIET_POLL_PATHS):
                return False
        return True


def main() -> None:
    import uvicorn
    ap = argparse.ArgumentParser(description="Harness web UI (launcher + monitor).")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--verbose-access", action="store_true",
                    help="Log every request, including the UI's live polling.")
    args = ap.parse_args()
    if not args.verbose_access:
        logging.getLogger("uvicorn.access").addFilter(_QuietPollingFilter())
    print(f"SecDevQA harness UI → http://localhost:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
