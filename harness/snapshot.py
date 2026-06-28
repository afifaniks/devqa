"""
SecDevQA — time-capped snapshot assembly for the snapshot_agent condition.

A Snapshot freezes the world at the moment the report was posted (thread created_at):
  * repo      — working tree checked out at the last default-branch commit before T
                (cached clone + one shared worktree per (repo, sha));
  * issues    — the mined issue corpus filtered to issues created <= T, with comments
                capped at T, and the SOURCE THREAD ITSELF EXCLUDED (leak control —
                pre-T duplicates remain findable by design: that is the retrieval task);
  * prs       — mined pull requests created <= T (reviews capped at T);
  * advisories— GHSA records (OSV format) from the local advisory-database clone that
                reference this repo OR carry a thread CVE/GHSA/OSV id as alias, published
                <= T; each record embeds its CVE (aliases) and CWE (cwe_ids) — no separate
                NVD/MITRE source needed.

No live web access anywhere — live NVD/GHSA would disclose the resolution and void the
time-cap (PLAN.md Phase 4).

Clones live in harness/cache/repos/<owner>__<repo>; worktrees in
harness/cache/worktrees/<owner>__<repo>/<sha12>; per-repo advisory indexes in
harness/cache/advisories/<owner>__<repo>.json. All cache content is reused across runs.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

# Artifacts are capped to a trailing window before report time T: issues/PRs/advisories
# older than this are dropped (a developer at T would not be triaging ancient threads,
# and it bounds the retrieval corpus for huge repos). Alias-matched advisories — the
# specific CVE/GHSA the gold answer cites — bypass the floor (still <= T).
WINDOW_DAYS = 730  # ~2 years

ROOT = Path(__file__).parent.parent
CACHE = ROOT / "harness" / "cache"
OUTPUT_DIR = ROOT / "output"
ADVISORY_DB = ROOT / "advisory-database"
# Released benchmark (rubric-bearing) is the eval source; fall back to the full
# corpus if it hasn't been built. Kept inline to avoid importing the LLM stack here.
BENCHMARK = ROOT / "dataset" / "security_benchmark_release.jsonl"
if not BENCHMARK.exists():
    BENCHMARK = ROOT / "dataset" / "security_benchmark_final.jsonl"


def _git(cwd: Path, *args: str, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}: {r.stderr.strip()[:300]}")
    return r.stdout


def repo_dirname(repo: str) -> str:
    return repo.replace("/", "__")


def window_start(before: str) -> str:
    """ISO timestamp WINDOW_DAYS before T; '' if T unparseable. Lower bound for the
    trailing artifact window (same Z-suffixed format as the corpus, so string-comparable)."""
    try:
        t = datetime.fromisoformat((before or "").replace("Z", "+00:00"))
    except ValueError:
        return ""
    return (t - timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Report-time metadata (thread created_at lives in the benchmark, not eval_pairs)
# ---------------------------------------------------------------------------

_bench_meta: dict[str, dict] | None = None


def thread_meta(thread_id: str) -> dict:
    """{created_at, number, repo} for a benchmark thread id (owner/repo/issue/N)."""
    global _bench_meta
    if _bench_meta is None:
        _bench_meta = {}
        with open(BENCHMARK, encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                _bench_meta[r["id"]] = {"created_at": r.get("created_at"),
                                        "number": r.get("number"), "repo": r.get("repo"),
                                        "hard_facts": r.get("hard_facts") or {}}
    if thread_id not in _bench_meta:
        raise KeyError(f"{thread_id} not in {BENCHMARK} — rebuild the benchmark?")
    return _bench_meta[thread_id]


# ---------------------------------------------------------------------------
# Repo at time T
# ---------------------------------------------------------------------------

def ensure_clone(repo: str) -> Path:
    dest = CACHE / "repos" / repo_dirname(repo)
    if (dest / ".git").exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  [snapshot] cloning {repo} (blobless, full history) ...")
    r = subprocess.run(["git", "clone", "--filter=blob:none",
                        f"https://github.com/{repo}.git", str(dest)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"clone {repo} failed: {r.stderr.strip()[:300]}")
    return dest


def commit_before(clone: Path, iso_ts: str) -> str:
    sha = _git(clone, "rev-list", "-1", f"--before={iso_ts}", "HEAD").strip()
    if not sha:
        raise RuntimeError(f"no commit before {iso_ts} in {clone}")
    return sha


def ensure_worktree(clone: Path, sha: str, repo: str) -> Path:
    dest = CACHE / "worktrees" / repo_dirname(repo) / sha[:12]
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    _git(clone, "worktree", "add", "--detach", str(dest), sha)
    return dest


# ---------------------------------------------------------------------------
# Issues / PRs at time T
# ---------------------------------------------------------------------------

def load_issues(repo: str, before: str, exclude_number: int | None) -> list[dict]:
    path = OUTPUT_DIR / repo_dirname(repo) / "issues.jsonl"
    if not path.exists():
        return []
    floor = window_start(before)
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            ca = d.get("created_at") or "9999"
            if ca > before:
                continue
            if floor and ca < floor:
                continue  # outside the trailing window
            if exclude_number is not None and d.get("number") == exclude_number:
                continue  # the question's own thread must not be visible
            comments = [c for c in (d.get("comments") or [])
                        if (c.get("created_at") or "9999") <= before]
            out.append({"number": d.get("number"), "title": d.get("title") or "",
                        "state": d.get("state"), "created_at": d.get("created_at"),
                        "labels": d.get("labels") or [], "body": d.get("body") or "",
                        "comments": comments})
    return out


def load_prs(repo: str, before: str) -> list[dict]:
    path = OUTPUT_DIR / repo_dirname(repo) / "pull_requests.jsonl"
    if not path.exists():
        return []
    floor = window_start(before)
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            ca = d.get("created_at") or "9999"
            if ca > before or (floor and ca < floor):
                continue
            reviews = [r for r in (d.get("reviews") or [])
                       if (r.get("submitted_at") or r.get("created_at") or "") <= before]
            out.append({"number": d.get("number"), "title": d.get("title") or "",
                        "created_at": d.get("created_at"),
                        "merged_at": d.get("merged_at") if (d.get("merged_at") or "9999") <= before else None,
                        "outcome": d.get("outcome"), "body": d.get("body") or "",
                        "labels": d.get("labels") or [], "reviews": reviews})
    return out


# ---------------------------------------------------------------------------
# Advisories at time T
# ---------------------------------------------------------------------------

def _advisory_index(repo: str) -> list[str]:
    """Paths of advisory JSON files referencing this repo (grep once, cache forever)."""
    idx_path = CACHE / "advisories" / f"{repo_dirname(repo)}.json"
    if idx_path.exists():
        return json.loads(idx_path.read_text())
    if not ADVISORY_DB.exists():
        return []
    print(f"  [snapshot] indexing advisory-database for {repo} (one-time) ...")
    r = subprocess.run(["grep", "-rl", f"github.com/{repo}", str(ADVISORY_DB / "advisories")],
                       capture_output=True, text=True)
    paths = [p for p in r.stdout.splitlines() if p.endswith(".json")]
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(json.dumps(paths))
    return paths


def _advisory_paths_for_ids(ids: list[str] | None) -> list[str]:
    """Advisory files whose id or alias matches any of `ids` (CVE/GHSA/OSV).
    Catches advisories the gold answer cites that the repo-URL grep index misses —
    a GHSA records its CVE under `aliases`, not necessarily a github.com/<repo> ref."""
    out = []
    cache_dir = CACHE / "advisories" / "by_id"
    for raw in ids or []:
        gid = (raw or "").strip()
        if not gid:
            continue
        cpath = cache_dir / f"{gid}.json"
        if cpath.exists():
            out += json.loads(cpath.read_text())
            continue
        if not ADVISORY_DB.exists():
            continue
        r = subprocess.run(["grep", "-rl", gid, str(ADVISORY_DB / "advisories")],
                           capture_output=True, text=True)
        paths = [p for p in r.stdout.splitlines() if p.endswith(".json")]
        cache_dir.mkdir(parents=True, exist_ok=True)
        cpath.write_text(json.dumps(paths))
        out += paths
    return out


def load_advisories(repo: str, before: str, alias_ids: list[str] | None = None) -> list[dict]:
    """GHSA records (OSV format) referencing this repo, published <= T. Each record
    embeds its CVE (via `aliases`) and CWE (via `database_specific.cwe_ids`) — no
    separate NVD/MITRE source needed. `alias_ids` (thread CVE/GHSA/OSV hard_facts)
    pulls in advisories matched by id when the repo-URL index misses them; still
    time-gated, so advisories disclosed after T stay out (leak control)."""
    alias_paths = set(_advisory_paths_for_ids(alias_ids))
    floor = window_start(before)
    out, seen = [], set()
    for p in list(_advisory_index(repo)) + list(alias_paths):
        if p in seen:
            continue
        seen.add(p)
        try:
            a = json.loads(Path(p).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        pub = a.get("published") or "9999"
        if pub > before:
            continue
        if floor and pub < floor and p not in alias_paths:
            continue  # outside window — but a gold-answer-cited advisory bypasses the floor
        ds = a.get("database_specific", {}) or {}
        out.append({"id": a.get("id"), "aliases": a.get("aliases") or [],
                    "published": a.get("published"),
                    "cwe_ids": ds.get("cwe_ids") or [],
                    "severity": ds.get("severity") or a.get("severity"),
                    "summary": a.get("summary") or "",
                    "details": a.get("details") or "",
                    "affected": a.get("affected") or [],
                    "references": [r.get("url") for r in (a.get("references") or [])]})
    return out


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

@dataclass
class Snapshot:
    repo: str
    report_time: str               # ISO — the time cap T
    excluded_issue: int | None
    commit_sha: str = ""
    worktree: Path | None = None   # None when the `code` group is disabled (LOO)
    clone: Path | None = None
    issues: list[dict] = field(default_factory=list)
    prs: list[dict] = field(default_factory=list)
    advisories: list[dict] = field(default_factory=list)


def build_snapshot(thread_id: str, groups: set[str]) -> Snapshot:
    """Assemble the time-capped snapshot for a thread, materializing only the artifact
    groups in `groups` (subset of {code, commits, issues, prs, advisory}) — the
    LOO/single-artifact gate of the selective-provision design."""
    meta = thread_meta(thread_id)
    repo, before = meta["repo"], meta["created_at"]
    snap = Snapshot(repo=repo, report_time=before, excluded_issue=meta.get("number"))
    if groups & {"code", "commits"}:
        snap.clone = ensure_clone(repo)
        snap.commit_sha = commit_before(snap.clone, before)
        snap.worktree = ensure_worktree(snap.clone, snap.commit_sha, repo)
    if "issues" in groups:
        snap.issues = load_issues(repo, before, meta.get("number"))
    if "prs" in groups:
        snap.prs = load_prs(repo, before)
    if "advisory" in groups:
        hf = meta.get("hard_facts") or {}
        alias_ids = ((hf.get("cve_ids") or []) + (hf.get("ghsa_ids") or [])
                     + (hf.get("osv_ids") or []))
        snap.advisories = load_advisories(repo, before, alias_ids)
    return snap
