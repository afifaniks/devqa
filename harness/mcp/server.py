"""
SecDevQA — MCP server exposing a time-capped snapshot to any agent.

This is the unified tool interface for both the built-in agent and containerized
claude-code. It runs as a stdio MCP server inside the per-item container and serves
the same typed, artifact-grouped tools the built-in agent already uses — by wrapping the
existing :class:`~harness.snapshot.tools.ToolBox`, so tool semantics, result truncation, and the
RQ4 per-call attribution log are identical to the in-process path.

Design invariants:
  * SINGLE backend — every tool routes through ``ToolBox.execute``; there is no second
    implementation of "read a file" / "search issues" to drift out of sync.
  * GROUP GATING (RQ3) — only the tools whose artifact group is enabled in the payload's
    ``config.json`` are registered. A disabled group's tools simply do not exist on the server,
    so an agent cannot call what it was not provisioned. The optional live-``web`` group is
    never exposed here: the container blocks egress, so there is no live internet to reach.
  * OFFLINE — the Snapshot is reconstructed from the mounted payload
    (:mod:`harness.snapshot.payload`); the server performs no clone, advisory-database, or
    network access. (Caveat: ``vuln_lookup`` still resolves ids over HTTP; under the container
    egress allowlist that succeeds only for ids already in the mounted on-disk cache — see the
    container materializer.)
  * OBSERVABLE — every call emits a ``tool_call``/``tool_result`` pair to the live-events file
    (:mod:`harness.mcp.events`) in the monitor UI's existing schema.

Run (env-configured, as the container launches it)::

    SECDEVQA_SNAPSHOT_DIR=/snapshot \\
    SECDEVQA_LIVE_EVENTS=/snapshot/live.jsonl \\
    python -m harness.mcp.server

or explicitly for local testing::

    python -m harness.mcp.server --snapshot-dir DIR --groups code,issues --live-events F
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from harness.mcp.events import EventLog
from harness.snapshot.payload import load_snapshot
from harness.snapshot.tools import TOOL_SCHEMAS, ToolBox

SERVER_NAME = "secdevqa-snapshot"

# Tool description text, sourced from the canonical schemas so it never drifts from the
# built-in agent's tool definitions. (The web group is intentionally excluded.)
_DESCRIPTIONS = {
    schema["function"]["name"]: schema["function"]["description"]
    for group, schemas in TOOL_SCHEMAS.items() if group != "web"
    for schema in schemas
}


def register_tools(mcp: FastMCP, box: ToolBox, groups: set[str], events: EventLog) -> list[str]:
    """Register every snapshot tool whose artifact group is in `groups`; returns their names.

    Each tool is a thin wrapper that emits a live event, routes through ``box.execute`` (which
    records the call for RQ4 and truncates the result), and emits the paired result event. The
    wrappers carry real type annotations so FastMCP derives correct JSON-Schema for each tool."""

    def dispatch(name: str, **kwargs) -> str:
        group = ToolBox.GROUP_OF_TOOL.get(name)
        events.tool_call(name, group, kwargs)
        result = box.execute(name, kwargs)
        events.tool_result(name, group, result)
        return result

    registered: list[str] = []

    def expose(fn):
        """Register `fn` as an MCP tool iff its artifact group is enabled for this run."""
        name = fn.__name__
        if ToolBox.GROUP_OF_TOOL.get(name) in groups:
            mcp.add_tool(fn, name=name, description=_DESCRIPTIONS.get(name))
            registered.append(name)
        return fn

    # ---- code -------------------------------------------------------------
    @expose
    def list_dir(path: str = ".") -> str:
        return dispatch("list_dir", path=path)

    @expose
    def read_file(path: str, start_line: int = 1, end_line: int = 200) -> str:
        return dispatch("read_file", path=path, start_line=start_line, end_line=end_line)

    @expose
    def search_code(pattern: str, path_glob: str = "") -> str:
        return dispatch("search_code", pattern=pattern, path_glob=path_glob)

    # ---- commits ----------------------------------------------------------
    @expose
    def git_log(path: str = "", n: int = 20) -> str:
        return dispatch("git_log", path=path, n=n)

    @expose
    def git_show(sha: str) -> str:
        return dispatch("git_show", sha=sha)

    # ---- issues -----------------------------------------------------------
    @expose
    def search_issues(query: str, max_results: int = 10) -> str:
        return dispatch("search_issues", query=query, max_results=max_results)

    @expose
    def get_issue(number: int) -> str:
        return dispatch("get_issue", number=number)

    # ---- prs --------------------------------------------------------------
    @expose
    def search_prs(query: str, max_results: int = 10) -> str:
        return dispatch("search_prs", query=query, max_results=max_results)

    @expose
    def get_pr(number: int) -> str:
        return dispatch("get_pr", number=number)

    # ---- advisory ---------------------------------------------------------
    @expose
    def search_advisories(query: str, max_results: int = 10) -> str:
        return dispatch("search_advisories", query=query, max_results=max_results)

    @expose
    def get_advisory(advisory_id: str) -> str:
        return dispatch("get_advisory", advisory_id=advisory_id)

    @expose
    def vuln_lookup(id: str) -> str:
        return dispatch("vuln_lookup", id=id)

    return registered


def build_server(box: ToolBox, groups: set[str], events: EventLog) -> tuple[FastMCP, list[str]]:
    """Assemble a configured (but not yet running) MCP server; returns it and its tool names."""
    mcp = FastMCP(SERVER_NAME)
    names = register_tools(mcp, box, groups, events)
    return mcp, names


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="SecDevQA snapshot MCP server (stdio).")
    ap.add_argument("--snapshot-dir", default=os.environ.get("SECDEVQA_SNAPSHOT_DIR"),
                    help="payload directory (env: SECDEVQA_SNAPSHOT_DIR)")
    ap.add_argument("--groups", default=os.environ.get("SECDEVQA_GROUPS"),
                    help="override enabled groups, comma-separated (env: SECDEVQA_GROUPS)")
    ap.add_argument("--live-events", default=os.environ.get("SECDEVQA_LIVE_EVENTS"),
                    help="live-events JSONL path (env: SECDEVQA_LIVE_EVENTS)")
    ap.add_argument("--repo-dir", default=os.environ.get("SECDEVQA_REPO_DIR"),
                    help="working clone the code/commit tools operate on; overrides the path "
                         "recorded in the payload (env: SECDEVQA_REPO_DIR)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if not args.snapshot_dir:
        raise SystemExit("--snapshot-dir (or SECDEVQA_SNAPSHOT_DIR) is required")

    snap, groups = load_snapshot(Path(args.snapshot_dir))
    if args.groups:
        groups = {g.strip() for g in args.groups.split(",") if g.strip()}
    # In the container the repository is a real clone the entrypoint checked out at the base
    # commit; the payload only carries the bare mirror it came from. Point the code/commit
    # tools at that clone so `search_code`/`git_log` see the same tree the agent's own tools do.
    if args.repo_dir and Path(args.repo_dir).is_dir():
        snap.worktree = Path(args.repo_dir)
        # Real history is present now, so prefer live git over the precomputed fallbacks.
        snap.commit_log, snap.commit_patches = "", {}

    events = EventLog(Path(args.live_events) if args.live_events else None)
    box = ToolBox(snap, groups)
    mcp, _names = build_server(box, groups, events)
    try:
        mcp.run()   # stdio transport; blocks until the client disconnects
    finally:
        events.close()


if __name__ == "__main__":
    main()
