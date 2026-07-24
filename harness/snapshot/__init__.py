"""
SecDevQA harness — the time-capped snapshot and the typed tools over it.

  builder.py       time-capped Snapshot assembly (repo@T, issues/PRs/advisories ≤ T)
  tools.py         one tool group per artifact type, plus the optional web group
  stream_agent.py  LangChain ReAct streaming layer the snapshot_agent runs on

The package re-exports the snapshot surface so callers can keep importing it as
``from harness.snapshot import build_snapshot, Snapshot``.
"""

from harness.snapshot.builder import (
    BENCHMARK,
    Snapshot,
    build_snapshot,
    thread_meta,
    window_start,
)

__all__ = ["BENCHMARK", "Snapshot", "build_snapshot", "thread_meta", "window_start"]
