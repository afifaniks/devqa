"""Launcher and process-management routes."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from harness.conditions.agent import condition_name as agent_condition_name
from harness.conditions.external import AGENTS as EXTERNAL_AGENTS
from harness.container import egress as egress_cfg
from harness.container.run import AGENT_ARGV as CONTAINER_AGENTS
from harness.container.run import DEFAULT_IMAGE as CONTAINER_IMAGE
from harness.core.paths import ROOT
from harness.core.runs import make_run_name, slugify
from harness.grading.grade import DEFAULT_JUDGE as GRADE_DEFAULT_JUDGE
from harness.snapshot.tools import ALL_GROUPS

from .shared import (
    LOGS_DIR,
    OUTPUT_DIR,
    PROCS,
    RUN_NAME_RE,
    launch_meta_path,
    model_config,
    totals,
)

router = APIRouter()

# Stage progress lines look like "[12/50] owner/repo/issue/3#1 ...".
_PROGRESS_RE = re.compile(r"\[(\d+)/(\d+)\]\s+(\S+)")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class LaunchBody(BaseModel):
    system: str                       # llm | agent | claude-code | opencode | container-<agent>
    model: str | None = None
    groups: list[str] | None = None   # agent + container; None → full snapshot
    web_search: bool = False          # agent + container; live-internet (+web)
    limit: int | None = None
    include_unapproved: bool = False
    max_steps: int | None = None
    grade_after: bool = False
    judge: str | None = None
    only_id: str | None = None        # run a single benchmark item
    run_name: str | None = None       # set to resume an existing run
    auth: str | None = None           # container only: auto | env | mount (default mount)


class EgressBody(BaseModel):
    providers: list[str]
    extra_domains: list[str]
    allow_ollama: bool


class GradeBody(BaseModel):
    judge: str | None = None
    force: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_name_is_active(run_name: str) -> bool:
    """True if any tracked subprocess with this run_name is still running."""
    return any(
        info["run_name"] == run_name and info["proc"].poll() is None
        for info in PROCS.values()
    )


def _base_run_name(body: LaunchBody) -> str:
    if body.system == "llm":
        return f"{slugify(body.model)}_no_context"
    if body.system == "agent":
        groups = set(body.groups) if body.groups else set(ALL_GROUPS)
        return f"{slugify(body.model)}_{agent_condition_name(groups, body.web_search)}"
    if body.system.startswith("container-"):
        agent = body.system[len("container-"):].replace("-", "_")
        return f"container_{agent}" + ("+web" if body.web_search else "")
    cond = f"external_{body.system.replace('-', '_')}"
    return f"{slugify(body.model) + '_' if body.model else ''}{cond}"


def _container_available() -> bool:
    """True when podman is present and the eval image has been built."""
    if shutil.which("podman") is None:
        return False
    try:
        return subprocess.run(["podman", "image", "exists", CONTAINER_IMAGE],
                              capture_output=True).returncode == 0
    except OSError:
        return False


def _full_run_name(body: LaunchBody) -> str:
    """Explicit run_name wins; else base + instance tag + timestamp."""
    return make_run_name(_base_run_name(body), body.only_id, body.run_name)


def _build_cmd(body: LaunchBody, run_name: str) -> list[str]:
    py = sys.executable
    common: list[str] = ["--run-name", run_name]
    if body.limit:
        common += ["--limit", str(body.limit)]
    if body.include_unapproved:
        common += ["--include-unapproved"]
    if body.only_id:
        common += ["--only-id", body.only_id]

    if body.system == "llm":
        if not body.model:
            raise HTTPException(400, "model is required for the bare-LLM system")
        cmd = [py, "-m", "harness", "answer",
               "--model", body.model, "--condition", "no_context", *common]
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
        if body.web_search:
            cmd += ["--web-search"]
        if body.max_steps:
            cmd += ["--max-steps", str(body.max_steps)]
    elif body.system.startswith("container-"):
        agent = body.system[len("container-"):]
        if agent not in CONTAINER_AGENTS:
            raise HTTPException(400, f"unknown container agent: {agent}")
        cmd = [py, "-m", "harness", "container", "--agent", agent,
               "--auth", body.auth or "mount", *common]
        groups = set(body.groups) if body.groups else set(ALL_GROUPS)
        bad = groups - set(ALL_GROUPS)
        if bad:
            raise HTTPException(400, f"unknown groups: {sorted(bad)}")
        if groups != set(ALL_GROUPS):
            cmd += ["--groups", ",".join(sorted(groups))]
        if body.web_search:
            cmd += ["--web"]
    elif body.system in EXTERNAL_AGENTS:
        cmd = [py, "-m", "harness", "external", "--agent", body.system, *common]
        if body.model:
            cmd += ["--model", body.model]
    else:
        raise HTTPException(400, f"unknown system: {body.system}")

    shell = " ".join(shlex.quote(c) for c in cmd)
    if body.grade_after:
        answers = OUTPUT_DIR / f"answers_{run_name}.jsonl"
        gcmd = [py, "-m", "harness", "grade", "--answers", str(answers)]
        if body.judge:
            gcmd += ["--judge", body.judge]
        shell += " && " + " ".join(shlex.quote(c) for c in gcmd)
    return ["bash", "-c", shell]


def _spawn(
    cmd: list[str],
    run_name: str,
    display: str,
    answers_path: Path | None,
    grades_path: Path | None,
) -> str:
    """Start a tracked subprocess, capturing stdout/stderr to a log file."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    proc_id = f"{ts}_{run_name}"
    log_path = LOGS_DIR / f"{proc_id}.log"
    log_fh = open(log_path, "w", encoding="utf-8")
    log_fh.write(f"$ {display}\n\n")
    log_fh.flush()
    proc = subprocess.Popen(
        cmd, cwd=ROOT,
        stdout=log_fh, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    PROCS[proc_id] = {
        "proc": proc,
        "run_name": run_name,
        "cmd": display,
        "log": str(log_path),
        "started": ts,
        "answers_path": str(answers_path) if answers_path else None,
        "grades_path": str(grades_path) if grades_path else None,
    }
    return proc_id


def _count_lines(path: str | None) -> int:
    try:
        if path and Path(path).exists():
            return sum(
                1 for ln in Path(path).read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
                if ln.strip()
            )
    except OSError:
        pass
    return 0


def _proc_progress(info: dict, tail: str, running: bool) -> dict:
    matches = _PROGRESS_RE.findall(tail)
    idx = total = current_qid = None
    if matches:
        idx, total, current_qid = matches[-1]
        idx, total = int(idx), int(total)
    answered = _count_lines(info.get("answers_path"))
    graded = _count_lines(info.get("grades_path"))
    has_grading = info.get("grades_path") is not None
    if not running:
        phase = "done"
    elif "Judge:" in tail and "\nGraded:" not in tail:
        phase = "grading"
    else:
        phase = "answering"
    live_done = graded if phase == "grading" else answered
    return {
        "current_qid": current_qid,
        "idx": idx,
        "total": total,
        "answered": answered,
        "graded": graded,
        "has_grading": has_grading,
        "live_done": live_done,
        "phase": phase,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/api/options")
def options():
    """What the launch form can offer."""
    return {
        "systems": [
            {
                "id": "llm",
                "label": "Bare LLM (no_context)",
                "needs_model": True,
                "has_groups": False,
                "has_web": False,
                "available": True,
            },
            {
                "id": "agent",
                "label": "Built-in snapshot agent (typed tools)",
                "needs_model": True,
                "has_groups": True,
                "has_web": True,
                "available": True,
            },
            *[
                {
                    "id": a,
                    "label": f"External agent: {a}",
                    "needs_model": False,
                    "has_groups": False,
                    "has_web": False,
                    "available": shutil.which(spec["cmd"][0]) is not None,
                }
                for a, spec in EXTERNAL_AGENTS.items()
            ],
            *[
                {
                    "id": f"container-{a}",
                    "label": f"Container: {a} (unified MCP, egress-locked)",
                    "needs_model": False,
                    "has_groups": True,
                    "has_web": True,
                    "has_egress": True,
                    "available": _container_available(),
                }
                for a in CONTAINER_AGENTS
            ],
        ],
        "groups": list(ALL_GROUPS),
        **model_config(),
        "totals": totals(),
    }


@router.get("/api/egress")
def get_egress():
    """Current egress allowlist config + the effective domain/host allowlist it produces."""
    cfg = egress_cfg.load_config()
    policy = egress_cfg.default_policy(web=False, config=cfg)
    return {
        "config": cfg,
        "available_providers": list(egress_cfg.PROVIDER_DOMAINS),
        "vuln_domains": egress_cfg.VULN_DOMAINS,
        "effective_domains": policy.domains,
        "hosts": policy.hosts,
    }


@router.put("/api/egress")
def put_egress(body: EgressBody):
    """Persist an edited egress allowlist; new container runs pick it up (no restart)."""
    cfg = egress_cfg.save_config(body.model_dump())
    policy = egress_cfg.default_policy(web=False, config=cfg)
    return {"config": cfg, "effective_domains": policy.domains, "hosts": policy.hosts}


@router.post("/api/launch")
def launch(body: LaunchBody):
    run_name = _full_run_name(body)
    cmd = _build_cmd(body, run_name)
    display = cmd[-1]
    answers = OUTPUT_DIR / f"answers_{run_name}.jsonl"
    jslug = slugify(body.judge or GRADE_DEFAULT_JUDGE)
    grades = OUTPUT_DIR / f"grades_{run_name}__judge-{jslug}.jsonl"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    launch_meta_path(run_name).write_text(
        json.dumps(
            {**body.model_dump(), "run_name": run_name}, indent=1
        )
    )
    proc_id = _spawn(
        cmd, run_name, display, answers, grades if body.grade_after else None
    )
    return {"ok": True, "proc_id": proc_id, "run_name": run_name, "cmd": display}


@router.post("/api/runs/{name}/resume")
def resume_run(name: str):
    """Re-launch under the existing name; finished items are kept."""
    if not RUN_NAME_RE.match(name):
        raise HTTPException(400, "invalid run name")
    if _run_name_is_active(name):
        raise HTTPException(
            409, f"run {name!r} is still in progress — stop it first"
        )
    meta_path = launch_meta_path(name)
    if not meta_path.exists():
        raise HTTPException(
            404,
            f"no launch metadata for run {name!r} — cannot resume"
            " (only runs launched from the UI can be resumed)",
        )
    meta = json.loads(meta_path.read_text())
    meta["run_name"] = name
    body = LaunchBody(**{k: v for k, v in meta.items() if k in LaunchBody.model_fields})
    cmd = _build_cmd(body, name)
    display = cmd[-1]
    answers = OUTPUT_DIR / f"answers_{name}.jsonl"
    jslug = slugify(body.judge or GRADE_DEFAULT_JUDGE)
    grades = OUTPUT_DIR / f"grades_{name}__judge-{jslug}.jsonl"
    proc_id = _spawn(
        cmd, name, display, answers, grades if body.grade_after else None
    )
    return {"ok": True, "proc_id": proc_id, "run_name": name, "cmd": display}


@router.post("/api/runs/{name}/grade")
def grade_run(name: str, body: GradeBody):
    """Grade (or re-grade) an existing run's answers, as a tracked process."""
    if not RUN_NAME_RE.match(name):
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
    jslug = slugify(body.judge or GRADE_DEFAULT_JUDGE)
    grades = OUTPUT_DIR / f"grades_{name}__judge-{jslug}.jsonl"
    proc_id = _spawn(gcmd, f"{name}_grade", display, answers, grades)
    return {"ok": True, "proc_id": proc_id, "run_name": f"{name}_grade", "cmd": display}


@router.get("/api/procs")
def procs():
    out = []
    for pid, info in sorted(PROCS.items(), reverse=True):
        p = info["proc"]
        rc = p.poll()
        tail = ""
        try:
            tail = Path(info["log"]).read_text(
                encoding="utf-8", errors="replace"
            )[-4000:]
        except OSError:
            pass
        out.append({
            "proc_id": pid,
            "run_name": info["run_name"],
            "cmd": info["cmd"],
            "started": info["started"],
            "running": rc is None,
            "returncode": rc,
            "log_tail": tail,
            **_proc_progress(info, tail, rc is None),
        })
    return {"procs": out}


@router.post("/api/procs/{proc_id}/stop")
def stop(proc_id: str):
    info = PROCS.get(proc_id)
    if not info:
        raise HTTPException(
            404, "unknown process (server restarted? stop it from the shell)"
        )
    p = info["proc"]
    if p.poll() is None:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
    return {"ok": True, "returncode": p.poll()}


@router.delete("/api/procs/{proc_id}")
def remove_proc(proc_id: str):
    """Drop a finished process from the list and delete its log."""
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
