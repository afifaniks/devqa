"""
SecDevQA — typed tools the snapshot agent can call, grouped by artifact type.

One tool group per artifact type, so "which artifact types did the agent consult" is a
count of tool calls by name (RQ4 attribution by construction — PLAN.md Phase 4):

  code      read_file, list_dir, search_code          (worktree at commit-before-T)
  commits   git_log, git_show                         (history capped at T by checkout;
                                                       git_show guarded to ancestors)
  issues    search_issues, get_issue                  (corpus <= T, source thread excluded)
  prs       search_prs, get_pr                        (corpus <= T)
  advisory  search_advisories, get_advisory           (GHSA snapshot <= T)

`artifacts_needed` vocabulary maps onto groups via ARTIFACT_TO_GROUP; the LOO /
single-artifact toggles of the selective-provision design (RQ3) enable/disable groups.
Every tool result is truncated to MAX_RESULT_CHARS.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from harness.snapshot import Snapshot

MAX_RESULT_CHARS = 5000

# artifacts_needed value -> tool group
ARTIFACT_TO_GROUP = {
    "code": "code", "dependency_manifest": "code", "documentation": "code",
    "commit_history": "commits",
    "pr_data": "prs",
    "issue_tracker": "issues", "prior_incident": "issues",
    "advisory": "advisory", "cve_cwe_db": "advisory",
    "external_reference": None,        # live web — not available under the time-cap
    "security_scan_logs": None, "ci_logs": None, "contributor_data": None,
}
ALL_GROUPS = ("code", "commits", "issues", "prs", "advisory")


def _trunc(s: str, n: int = MAX_RESULT_CHARS) -> str:
    return s if len(s) <= n else s[:n] + f"\n... [truncated, {len(s)} chars total]"


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else f"ERROR: {r.stderr.strip()[:300]}"


class ToolBox:
    """Executes tool calls against a Snapshot; records per-tool call counts."""

    def __init__(self, snap: Snapshot, groups: set[str]):
        self.snap = snap
        self.groups = groups
        self.calls: list[dict] = []

    # ---- code group -------------------------------------------------------

    def _safe_path(self, rel: str) -> Path | None:
        root = self.snap.worktree.resolve()
        p = (root / rel).resolve()
        return p if str(p).startswith(str(root)) else None

    def read_file(self, path: str, start_line: int = 1, end_line: int = 200) -> str:
        p = self._safe_path(path)
        if p is None or not p.is_file():
            return f"ERROR: no such file in snapshot: {path}"
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            return f"ERROR: {exc}"
        start, end = max(1, int(start_line)), min(len(lines), int(end_line))
        body = "\n".join(f"{i}\t{lines[i-1]}" for i in range(start, end + 1))
        return _trunc(f"{path} (lines {start}-{end} of {len(lines)})\n{body}")

    def list_dir(self, path: str = ".") -> str:
        p = self._safe_path(path)
        if p is None or not p.is_dir():
            return f"ERROR: no such directory in snapshot: {path}"
        entries = sorted(x.name + ("/" if x.is_dir() else "") for x in p.iterdir()
                         if x.name != ".git")
        return _trunc("\n".join(entries) or "(empty)")

    def search_code(self, pattern: str, path_glob: str = "") -> str:
        args = ["grep", "-n", "-I", "--max-count=5", "-e", pattern]
        if path_glob:
            args += ["--", path_glob]
        return _trunc(_git(self.snap.worktree, *args) or "(no matches)")

    # ---- commits group ----------------------------------------------------

    def git_log(self, path: str = "", n: int = 20) -> str:
        args = ["log", f"--max-count={min(int(n), 50)}",
                "--date=iso", "--pretty=format:%h %ad %an %s"]
        if path:
            args += ["--", path]
        return _trunc(_git(self.snap.worktree, *args) or "(no commits)")

    def git_show(self, sha: str) -> str:
        if not re.fullmatch(r"[0-9a-fA-F]{6,40}", sha.strip()):
            return "ERROR: pass a commit SHA (6-40 hex chars)"
        sha = sha.strip()
        # Time-cap guard: the clone contains post-report commits; only ancestors of the
        # snapshot commit are visible.
        chk = subprocess.run(["git", "merge-base", "--is-ancestor", sha, "HEAD"],
                             cwd=self.snap.worktree, capture_output=True)
        if chk.returncode != 0:
            return f"ERROR: commit {sha} not found in the repository as of {self.snap.report_time}"
        return _trunc(_git(self.snap.worktree, "show", "--stat", "--patch", sha))

    # ---- issues / prs groups ----------------------------------------------

    @staticmethod
    def _kw_search(records: list[dict], query: str, fields, top: int) -> list[dict]:
        terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
        scored = []
        for r in records:
            text = " ".join(str(f(r)) for f in fields).lower()
            score = sum(text.count(t) for t in terms)
            if score:
                scored.append((score, r))
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:top]]

    def search_issues(self, query: str, max_results: int = 10) -> str:
        hits = self._kw_search(
            self.snap.issues, query,
            [lambda r: r["title"], lambda r: r["body"][:2000],
             lambda r: " ".join(r["labels"])], int(max_results))
        if not hits:
            return "(no matching issues in the tracker as of the report date)"
        return _trunc("\n".join(
            f"#{r['number']} [{r['state']}] {r['created_at'][:10]} {r['title']}"
            f" — {r['body'][:120]!r}" for r in hits))

    def get_issue(self, number: int) -> str:
        for r in self.snap.issues:
            if r["number"] == int(number):
                parts = [f"#{r['number']} {r['title']} [{r['state']}]"
                         f" created {r['created_at']} labels={r['labels']}",
                         r["body"], ""]
                for c in r["comments"]:
                    parts.append(f"--- {c.get('author')} at {c.get('created_at')} ---\n"
                                 f"{c.get('body', '')}")
                return _trunc("\n".join(parts))
        return f"ERROR: issue #{number} not found (as of {self.snap.report_time})"

    def search_prs(self, query: str, max_results: int = 10) -> str:
        hits = self._kw_search(
            self.snap.prs, query,
            [lambda r: r["title"], lambda r: r["body"][:2000]], int(max_results))
        if not hits:
            return "(no matching pull requests as of the report date)"
        return _trunc("\n".join(
            f"#{r['number']} [{r['outcome'] or 'open'}] {r['created_at'][:10]}"
            f"{' merged ' + r['merged_at'][:10] if r['merged_at'] else ''} {r['title']}"
            for r in hits))

    def get_pr(self, number: int) -> str:
        for r in self.snap.prs:
            if r["number"] == int(number):
                parts = [f"PR #{r['number']} {r['title']} [{r['outcome'] or 'open'}]"
                         f" created {r['created_at']} merged={r['merged_at']}",
                         r["body"]]
                for rev in r["reviews"][:10]:
                    parts.append(f"review by {rev.get('author')}: {rev.get('state')}"
                                 f" — {str(rev.get('body', ''))[:300]}")
                return _trunc("\n".join(parts))
        return f"ERROR: PR #{number} not found (as of {self.snap.report_time})"

    # ---- advisory group ----------------------------------------------------

    def search_advisories(self, query: str, max_results: int = 10) -> str:
        hits = self._kw_search(
            self.snap.advisories, query,
            [lambda r: r["id"], lambda r: " ".join(r["aliases"]),
             lambda r: r["summary"], lambda r: r["details"][:2000]], int(max_results))
        if not hits:
            return "(no matching advisories published before the report date)"
        return _trunc("\n".join(
            f"{r['id']} ({', '.join(r['aliases'])}) [{r['severity']}]"
            f" published {str(r['published'])[:10]} — {r['summary'][:140]}" for r in hits))

    def get_advisory(self, advisory_id: str) -> str:
        aid = advisory_id.strip().upper()
        for r in self.snap.advisories:
            if r["id"].upper() == aid or aid in [a.upper() for a in r["aliases"]]:
                return _trunc(
                    f"{r['id']} aliases={r['aliases']} cwe={r.get('cwe_ids') or []}"
                    f" severity={r['severity']}"
                    f" published={r['published']}\n\n{r['summary']}\n\n{r['details']}\n\n"
                    f"affected: {r['affected']}\nreferences: {r['references']}")
        return f"ERROR: advisory {advisory_id} not found (as of {self.snap.report_time})"

    # ---- dispatch -----------------------------------------------------------

    GROUP_OF_TOOL = {
        "read_file": "code", "list_dir": "code", "search_code": "code",
        "git_log": "commits", "git_show": "commits",
        "search_issues": "issues", "get_issue": "issues",
        "search_prs": "prs", "get_pr": "prs",
        "search_advisories": "advisory", "get_advisory": "advisory",
    }

    def execute(self, name: str, args: dict) -> str:
        group = self.GROUP_OF_TOOL.get(name)
        if group is None or group not in self.groups:
            result = f"ERROR: tool {name} is not available in this condition"
        else:
            try:
                result = getattr(self, name)(**args)
            except TypeError as exc:
                result = f"ERROR: bad arguments for {name}: {exc}"
            except Exception as exc:  # tool errors must not kill the run
                result = f"ERROR: {exc}"
        self.calls.append({"tool": name, "group": group, "args": args,
                           "result_chars": len(result)})
        return result


# ---------------------------------------------------------------------------
# OpenAI-style tool schemas (LiteLLM-compatible), emitted only for active groups
# ---------------------------------------------------------------------------

def _schema(name: str, desc: str, props: dict, required: list[str]) -> dict:
    return {"type": "function",
            "function": {"name": name, "description": desc,
                         "parameters": {"type": "object", "properties": props,
                                        "required": required}}}


_S = {"type": "string"}
_I = {"type": "integer"}

TOOL_SCHEMAS = {
    "code": [
        _schema("list_dir", "List a directory of the repository snapshot.",
                {"path": _S}, []),
        _schema("read_file", "Read a file from the repository snapshot (line-numbered).",
                {"path": _S, "start_line": _I, "end_line": _I}, ["path"]),
        _schema("search_code", "Search tracked files for a regex (git grep).",
                {"pattern": _S, "path_glob": _S}, ["pattern"]),
    ],
    "commits": [
        _schema("git_log", "Commit history (most recent first), optionally for a path.",
                {"path": _S, "n": _I}, []),
        _schema("git_show", "Show one commit's message, stat and patch by SHA.",
                {"sha": _S}, ["sha"]),
    ],
    "issues": [
        _schema("search_issues", "Keyword-search the project's issue tracker.",
                {"query": _S, "max_results": _I}, ["query"]),
        _schema("get_issue", "Read a full issue thread by number.",
                {"number": _I}, ["number"]),
    ],
    "prs": [
        _schema("search_prs", "Keyword-search the project's pull requests.",
                {"query": _S, "max_results": _I}, ["query"]),
        _schema("get_pr", "Read a pull request (body + reviews) by number.",
                {"number": _I}, ["number"]),
    ],
    "advisory": [
        _schema("search_advisories",
                "Keyword-search GitHub security advisories for this project.",
                {"query": _S, "max_results": _I}, ["query"]),
        _schema("get_advisory", "Read a full advisory by GHSA/CVE id.",
                {"advisory_id": _S}, ["advisory_id"]),
    ],
}


def schemas_for(groups: set[str]) -> list[dict]:
    out = []
    for g in ALL_GROUPS:
        if g in groups:
            out.extend(TOOL_SCHEMAS[g])
    return out
