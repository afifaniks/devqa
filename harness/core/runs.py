"""
SecDevQA harness — shared run plumbing for every system-under-test.

Item selection, run naming, the concurrent-run lock, and resume support are common to
the answer/agent/container conditions (and read by the monitor launcher), so they live
here rather than in any one command module.
"""

from __future__ import annotations

import fcntl
import json
import re
from datetime import datetime
from pathlib import Path
from typing import IO


def slugify(model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", model).strip("-")


def iter_items(threads: list[dict], include_unapproved: bool) -> list[tuple[dict, dict]]:
    """Flatten threads into (thread, qa_pair) items, approved threads only by default."""
    items = []
    for t in threads:
        if t.get("error") or not t.get("qa_pairs"):
            continue
        if not include_unapproved and not t.get("approved"):
            continue
        for p in t["qa_pairs"]:
            items.append((t, p))
    return items


def _parse_ids(only_id: str) -> list[str]:
    """Split an --only-id value into ids. Accepts a single id or a comma-separated
    list (UI 'run one' or 'run selected subset')."""
    return [s.strip() for s in only_id.split(",") if s.strip()]


def select_items(items: list[tuple[dict, dict]],
                 only_id: str | None) -> list[tuple[dict, dict]]:
    """Restrict to a chosen set of benchmark instances by qid or thread_id.

    `only_id` is a single id or a comma-separated list (UI 'run one'/'run selected')."""
    if not only_id:
        return items
    wanted = set(_parse_ids(only_id))
    keep = [(t, p) for (t, p) in items
            if p.get("qid") in wanted or t.get("thread_id") in wanted]
    if not keep:
        raise SystemExit(
            f"--only-id {only_id!r} matched no item — pass a qid or thread_id "
            f"(or comma-separated list; add --include-unapproved if the thread "
            f"is not yet approved)")
    return keep


def instance_slug(only_id: str) -> str:
    """Compact tag for a single-instance run, e.g. 'issue_8494_q1'. For a
    multi-id selection, a 'selN' tag naming the count instead."""
    ids = _parse_ids(only_id)
    if len(ids) > 1:
        return f"sel{len(ids)}"
    s = (ids[0] if ids else only_id).replace("#", "_q")
    parts = s.split("/")
    tail = "_".join(parts[-2:]) if len(parts) >= 2 else s
    return re.sub(r"[^A-Za-z0-9_.-]", "_", tail)


def make_run_name(base: str, only_id: str | None = None,
                  run_name: str | None = None) -> str:
    """Unique, log-everything run name. Explicit `run_name` (from the UI launcher)
    wins; otherwise base + instance tag (if any) + timestamp — so every launch lands
    in its own answers_<run>.jsonl and nothing is ever overwritten."""
    if run_name:
        return run_name
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    parts = [base] + ([instance_slug(only_id)] if only_id else []) + [ts]
    return "_".join(parts)


def acquire_run_lock(output_path: Path) -> IO:
    """Acquire an exclusive non-blocking flock on <output_path>.lock.
    Raises SystemExit if another process already holds it (concurrent run guard)."""
    lock_path = output_path.with_suffix(".lock")
    lock_fh = open(lock_path, "w")
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        lock_fh.close()
        raise SystemExit(
            f"Run already in progress — another process holds the output lock.\n"
            f"  Lock: {lock_path}\n"
            f"  If no other process is running, delete the lock file to reset."
        )
    return lock_fh  # caller must keep this open for the lock to remain held


def resume_state(output_path: Path) -> tuple[list[dict], set[str]]:
    """Resume support: if `output_path` exists, keep every SUCCESSFUL record and skip
    its qid. Corrupt/partial lines (from an interrupted prior run) are skipped with a
    warning — those items are re-run. A fresh run with no existing file starts empty."""
    if not output_path.exists():
        return [], set()
    rows: list[dict] = []
    bad = 0
    with open(output_path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1
                print(f"  [resume] Skipping corrupt line {lineno} — item will be re-run")
    if bad:
        print(f"  [resume] {bad} corrupt line(s) skipped")
    good = [r for r in rows if not r.get("error")]
    done = {r["qid"] for r in good if r.get("qid")}
    return good, done
