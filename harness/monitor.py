"""
SecDevQA harness — web UI: launch evaluation runs and monitor them live.

A standalone FastAPI app (port 8766) over harness/output/. Two halves:

  * Launcher — pick a system (bare LLM / built-in snapshot agent / claude-code /
    opencode), model, artifact-group context selection, limit, and optional
    auto-grading; the server spawns the corresponding `python -m harness ...` CLI as a
    subprocess (logged to harness/output/logs/), so everything the UI does is exactly
    reproducible from the shell.
  * Monitor — read-only polling over the answers_*/grades_* JSONL files and transcripts;
    tolerant of half-written lines, needs no coordination with runs.

Usage:
  python -m harness ui              # http://localhost:8766
  python -m harness ui --port 9000
"""

from __future__ import annotations

import argparse
import json
import os
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
from pydantic import BaseModel

from harness.agent import condition_name as agent_condition_name
from harness.answer import slugify
from harness.external import AGENTS as EXTERNAL_AGENTS
from harness.tools import ALL_GROUPS

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "harness" / "output"
LOGS_DIR = OUTPUT_DIR / "logs"
PAIRS_FILE = ROOT / "dataset" / "eval_pairs.jsonl"
HTML_FILE = Path(__file__).parent / "ui.html"

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


def totals() -> dict:
    threads = read_jsonl(PAIRS_FILE)
    return {
        "items_total": sum(len(t.get("qa_pairs") or [])
                           for t in threads if not t.get("error")),
        "items_approved": sum(len(t.get("qa_pairs") or [])
                              for t in threads
                              if t.get("approved") and not t.get("error")),
    }


# ---------------------------------------------------------------------------
# Monitoring APIs
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def page():
    return HTMLResponse(HTML_FILE.read_text(encoding="utf-8"))


@app.get("/api/runs")
def runs():
    now = time.time()
    out = []
    for path in sorted(OUTPUT_DIR.glob("answers_*.jsonl")):
        name = path.stem.removeprefix("answers_")
        recs = read_jsonl(path)
        ok = [r for r in recs if not r.get("error")]
        outcomes: dict[str, int] = {}
        n_halluc = n_flags = n_graded = 0
        for g in read_jsonl(OUTPUT_DIR / f"grades_{name}.jsonl"):
            if g.get("error"):
                continue
            n_graded += 1
            outcomes[g.get("outcome", "?")] = outcomes.get(g.get("outcome", "?"), 0) + 1
            n_halluc += 1 if g.get("hallucinated") else 0
            n_flags += 1 if g.get("flags") else 0
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
def run_detail(name: str, tail: int = 50):
    path = OUTPUT_DIR / f"answers_{name}.jsonl"
    if not path.exists():
        raise HTTPException(404, f"no run named {name}")
    grades = {g["qid"]: g
              for g in read_jsonl(OUTPUT_DIR / f"grades_{name}.jsonl")
              if not g.get("error")}
    items = []
    for r in read_jsonl(path)[-tail:]:
        g = grades.get(r.get("qid"))
        judge = (g or {}).get("judge") or {}
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
            "question": (r.get("question") or "")[:600],
            "response": (r.get("response") or "")[:4000],
            "outcome": (g or {}).get("outcome"),
            "hallucinated": (g or {}).get("hallucinated"),
            "flags": (g or {}).get("flags"),
            "claims": judge.get("claims"),
            "hallucinations": judge.get("hallucinations"),
            "hard_facts": (g or {}).get("hard_facts"),
        })
    items.reverse()  # newest first
    return {"name": name, "items": items}


@app.get("/api/transcript/{name}/{qid_slug}")
def transcript(name: str, qid_slug: str):
    path = OUTPUT_DIR / "transcripts" / name / f"{qid_slug}.json"
    if not path.exists():
        raise HTTPException(404, "no transcript for this item")
    return json.loads(path.read_text(encoding="utf-8"))


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
        "model_suggestions": ["gpt-5.4-mini", "gpt-5.4",
                              "anthropic/claude-sonnet-4-6",
                              "anthropic/claude-opus-4-8",
                              "ollama/qwen3.6:latest"],
        "judge_suggestions": ["gpt-5.4", "anthropic/claude-opus-4-8"],
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
        shell += " && " + " ".join(shlex.quote(c) for c in gcmd)
    return ["bash", "-c", shell], run_name


@app.post("/api/launch")
def launch(body: LaunchBody):
    cmd, run_name = _build_cmd(body)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    proc_id = f"{ts}_{run_name}"
    log_path = LOGS_DIR / f"{proc_id}.log"
    log_fh = open(log_path, "w", encoding="utf-8")
    log_fh.write(f"$ {cmd[-1]}\n\n")
    log_fh.flush()
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log_fh, stderr=subprocess.STDOUT,
                            start_new_session=True)
    PROCS[proc_id] = {"proc": proc, "run_name": run_name, "cmd": cmd[-1],
                      "log": str(log_path), "started": ts}
    return {"ok": True, "proc_id": proc_id, "run_name": run_name, "cmd": cmd[-1]}


@app.get("/api/procs")
def procs():
    out = []
    for pid, info in sorted(PROCS.items(), reverse=True):
        p = info["proc"]
        rc = p.poll()
        tail = ""
        try:
            tail = Path(info["log"]).read_text(
                encoding="utf-8", errors="replace")[-3000:]
        except OSError:
            pass
        out.append({"proc_id": pid, "run_name": info["run_name"],
                    "cmd": info["cmd"], "started": info["started"],
                    "running": rc is None, "returncode": rc, "log_tail": tail})
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


def main() -> None:
    import uvicorn
    ap = argparse.ArgumentParser(description="Harness web UI (launcher + monitor).")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()
    print(f"SecDevQA harness UI → http://localhost:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
