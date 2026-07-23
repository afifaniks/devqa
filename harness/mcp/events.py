"""
SecDevQA — live tool-event emitter for the MCP snapshot server.

The MCP server is the single choke point through which every agent tool call passes, so it is
also the natural place to record what the agent is doing while it works. This module appends
one JSON line per event to a live-events file, in EXACTLY the schema
:mod:`harness.snapshot.stream_agent` already emits::

    {"t": "tool_call",   "step": n, "tool": name, "group": grp, "args": {...}}
    {"t": "tool_result", "step": n, "tool": name, "group": grp, "chars": len, "result": "..."}

``tool_result`` additionally carries the verbatim ``result`` — this file is the only durable
record of what a containerized agent saw, and the final transcript is rebuilt from it.
``GET /api/live`` drops that field on the way out, so the UI's live poll is unaffected.

Because the schema is identical, the monitor UI's live view (``GET /api/live/{run}/{qid}``,
which tails ``transcripts/<run>/<qid>.live.jsonl``) renders container tool activity with no
changes. When the file is bind-mounted from the container to that host path, tool calls made
inside the sandbox stream to the UI in real time.

`EventLog(None)` is a no-op sink, so callers that do not want live events (tests, ad-hoc runs)
pay nothing and need no branching.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class EventLog:
    """Append-only live-event writer. A ``None`` path makes every method a no-op."""

    def __init__(self, path: Path | None):
        self._fh = None
        self._step = 0
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = path.open("a", encoding="utf-8")

    # -- lifecycle ----------------------------------------------------------

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> "EventLog":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # -- emit ---------------------------------------------------------------

    def _write(self, event: dict) -> None:
        if self._fh is None:
            return
        event.setdefault("ts", datetime.now(timezone.utc).isoformat(timespec="seconds"))
        self._fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        self._fh.flush()

    def tool_call(self, tool: str, group: str | None, args: dict) -> int:
        """Record the start of a tool call; returns its step index (paired with the result)."""
        self._step += 1
        self._write({"t": "tool_call", "step": self._step,
                     "tool": tool, "group": group, "args": args})
        return self._step

    def tool_result(self, tool: str, group: str | None, result: str) -> None:
        """Record a tool's OUTPUT verbatim.

        The full text is kept (already bounded by ``ToolBox``'s MAX_RESULT_CHARS) because
        this file is the only durable record of what the containerized agent actually saw
        — the final transcript is assembled from it. ``/api/live`` strips ``result`` before
        serving, so the UI's poll stays as light as it was when only ``chars`` was here."""
        self._write({"t": "tool_result", "step": self._step, "tool": tool,
                     "group": group, "chars": len(result), "result": result})

    def note(self, kind: str, **fields) -> None:
        """Emit a free-form lifecycle marker (e.g. ``start``/``done``) for the UI timeline."""
        self._write({"t": kind, **fields})
