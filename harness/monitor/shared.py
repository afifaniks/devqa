"""Shared state and helpers for the monitor package."""

from __future__ import annotations

import json
import re
from pathlib import Path

from harness.core.paths import (
    FINAL_BENCHMARK,
    MODELS_CONFIG,
    OUTPUT_DIR,
    RELEASE_BENCHMARK,
)

LOGS_DIR = OUTPUT_DIR / "logs"
PAIRS_FILE = FINAL_BENCHMARK
RELEASE_FILE = RELEASE_BENCHMARK

ACTIVE_SECS = 90  # answers file modified within this window → run shown as live

# Launched processes, by id. In-memory by design — runs are plain CLI processes
# and survive a UI restart; only their stop-buttons are lost after restart.
PROCS: dict[str, dict] = {}

# Run names are produced by slugify() + condition_name(): word chars, dot, dash.
RUN_NAME_RE = re.compile(r"^[A-Za-z0-9._+-]+$")
_JUDGE_SLUG_RE = re.compile(r"__judge-(.+)\.jsonl$")

_MODELS_FALLBACK = {
    "model_suggestions": [
        "openai/gpt-5.4-mini",
        "anthropic/claude-sonnet-4-6",
        "ollama/gemma4:31b",
    ],
    "judge_suggestions": ["openai/gpt-5.4", "anthropic/claude-opus-4-8"],
}


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
    """The released benchmark when built, else the full corpus."""
    return RELEASE_FILE if RELEASE_FILE.exists() else PAIRS_FILE


def grade_files(name: str) -> list[Path]:
    """All grade files for a run, newest first."""
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
        key = g.get("outcome", "?")
        outcomes[key] = outcomes.get(key, 0) + 1
        nh += 1 if g.get("hallucinated") else 0
        nf += 1 if g.get("flags") else 0
        if g.get("judge_model"):
            judges.add(g["judge_model"])
    judge = "mixed" if len(judges) > 1 else (next(iter(judges)) if judges else None)
    return {
        "slug": _slug_of(path),
        "judge_model": judge,
        "n_graded": n,
        "outcomes": outcomes,
        "n_hallucinated": nh,
        "n_flagged": nf,
    }


def grades_for(
    name: str, judge: str | None = None
) -> tuple[dict[str, dict], str | None]:
    """(qid → grade record, judge-slug) for one run, most-recent grading by default."""
    fs = grade_files(name)
    if not fs:
        return {}, None
    chosen = next((p for p in fs if judge and _slug_of(p) == judge), fs[0])
    grades = {
        g["qid"]: g
        for g in read_jsonl(chosen)
        if g.get("qid") and not g.get("error")
    }
    return grades, _slug_of(chosen)


def model_config() -> dict:
    """Launcher dropdown suggestions from models.json (live-reloaded, no restart)."""
    try:
        cfg = json.loads(MODELS_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(_MODELS_FALLBACK)
    return {
        "model_suggestions": (
            cfg.get("model_suggestions") or _MODELS_FALLBACK["model_suggestions"]
        ),
        "judge_suggestions": (
            cfg.get("judge_suggestions") or _MODELS_FALLBACK["judge_suggestions"]
        ),
    }


def totals() -> dict:
    """Item counts from the benchmark the UI browses."""
    threads = read_jsonl(benchmark_source())
    return {
        "items_total": sum(
            len(t.get("qa_pairs") or [])
            for t in threads
            if not t.get("error")
        ),
        "items_approved": sum(
            len(t.get("qa_pairs") or [])
            for t in threads
            if t.get("approved", True) and not t.get("error")
        ),
    }


def launch_meta_path(run_name: str) -> Path:
    return OUTPUT_DIR / f"answers_{run_name}.launch.json"
