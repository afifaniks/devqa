"""
SecDevQA — host-side materialization of a container-ready snapshot payload.

The container is offline (egress is allowlisted to the model API and the vuln-resolution hosts
only), so everything an agent may need from the repository must be baked into the payload here,
on the host, where the cached clone and network are available. This module turns a
:class:`~harness.snapshot.builder.Snapshot` into a directory the container mounts read-only and
the in-container MCP server (:mod:`harness.mcp.server`) reconstructs verbatim.

What it produces (only the enabled artifact groups are materialized):

  code     ``repo/`` — the tree at ``commit_sha`` exported with ``git archive`` and wrapped in a
           FRESH single-commit git repo. This is offline-complete (all files present, ``git grep``
           and file reads work with no network) AND airtight by construction: the repo has no
           ancestor or future history, so even an agent's own ``git log`` sees only the snapshot.
           (A ``git bundle`` from the blobless cache is NOT offline-complete — verified — hence
           this approach.)

  commits  ``data/commit_log.txt`` + ``data/commit_patches.json`` — real history, precomputed
           from the clone. Only ANCESTORS of ``commit_sha`` are included: a thread's fix commit
           typically postdates the report, and shipping its patch would leak the resolution.
           ``git_log`` is served from the log; ``git_show`` from the patch store (bounded window).

  issues / prs / advisory  serialized by :mod:`harness.snapshot.payload` from the Snapshot lists.

The build reuses the existing clone/worktree/advisory cache, so materialization is cheap on a
warm cache (only the archive + a bounded set of ``git show`` calls do real work).
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from harness.snapshot.builder import Snapshot, build_snapshot
from harness.snapshot.payload import dump_snapshot
from harness.snapshot.tools import ALL_GROUPS

# Bounds for the precomputed `commits` history. Log entries are commit metadata (free from a
# blobless clone); patches require blobs (lazy-fetched on the host at build time), so their
# window is smaller to bound network/time. Both cover the recent history an agent at time T
# would plausibly inspect; older commits fall back to a graceful "not available offline".
DEFAULT_LOG_COMMITS = 200
DEFAULT_PATCH_COMMITS = 40

# Deterministic identity for the synthetic snapshot commit (never depends on user git config).
_GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "SecDevQA", "GIT_AUTHOR_EMAIL": "snapshot@secdevqa.local",
    "GIT_COMMITTER_NAME": "SecDevQA", "GIT_COMMITTER_EMAIL": "snapshot@secdevqa.local",
}


def _run(cmd: list[str], cwd: Path, env: dict | None = None,
         stdin: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True,
                          env=env, check=True)


def _build_snapshot_repo(clone: Path, commit_sha: str, repo_dest: Path) -> None:
    """Export the tree at `commit_sha` into a fresh single-commit git repo at `repo_dest`."""
    repo_dest.mkdir(parents=True, exist_ok=True)
    archive = _run(["git", "archive", commit_sha], cwd=clone)
    _run(["tar", "-x", "-C", str(repo_dest)], cwd=clone, stdin=archive.stdout)
    env = {**os.environ, **_GIT_IDENTITY}
    _run(["git", "-c", "init.defaultBranch=snapshot", "init", "-q"], cwd=repo_dest, env=env)
    _run(["git", "add", "-A"], cwd=repo_dest, env=env)
    _run(["git", "commit", "-q", "-m", f"snapshot at {commit_sha}"], cwd=repo_dest, env=env)


def _git_out(clone: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=clone, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def _precompute_history(clone: Path, commit_sha: str, log_n: int,
                        patch_n: int) -> tuple[str, dict[str, str]]:
    """Return (commit_log, {short_sha: patch}) for ancestors of `commit_sha` only.

    Starting the walk at ``commit_sha`` bounds it to ancestors, so nothing after the report
    time is ever included — the offline analogue of the live git_show ancestor guard."""
    commit_log = _git_out(clone, "log", f"--max-count={log_n}", "--date=iso",
                          "--pretty=format:%h %ad %an %s", commit_sha)
    shas = _git_out(clone, "rev-list", f"--max-count={patch_n}", commit_sha).split()
    patches: dict[str, str] = {}
    for sha in shas:
        # Blobs are lazy-fetched here on the host (network available); offline in the container.
        out = _git_out(clone, "show", "--stat", "--patch", sha)
        if out:
            patches[sha[:12]] = out
    return commit_log, patches


def materialize_payload(thread_id: str, groups: set[str], dest: Path,
                        log_commits: int = DEFAULT_LOG_COMMITS,
                        patch_commits: int = DEFAULT_PATCH_COMMITS) -> dict:
    """Build the container-ready payload for `thread_id` at `dest`; returns a small metadata dict.

    `groups` selects which artifact groups to materialize (the RQ3 provision set). The result is
    a directory ready to bind-mount read-only into the container at a fixed path."""
    snap: Snapshot = build_snapshot(thread_id, groups)
    dest.mkdir(parents=True, exist_ok=True)

    if "code" in groups and snap.clone is not None and snap.commit_sha:
        _build_snapshot_repo(snap.clone, snap.commit_sha, dest / "repo")

    if "commits" in groups and snap.clone is not None and snap.commit_sha:
        snap.commit_log, snap.commit_patches = _precompute_history(
            snap.clone, snap.commit_sha, log_commits, patch_commits)

    # The host clone/worktree paths are meaningless inside the container; the offline repo (if
    # any) is embedded at dest/repo and resolved by convention. Drop the host references so the
    # payload is self-contained and portable.
    snap.worktree = None
    snap.clone = None
    dump_snapshot(snap, dest, groups)

    return {
        "thread_id": thread_id,
        "repo": snap.repo,
        "report_time": snap.report_time,
        "commit_sha": snap.commit_sha,
        "groups": sorted(groups),
        "n_issues": len(snap.issues),
        "n_prs": len(snap.prs),
        "n_advisories": len(snap.advisories),
        "n_commit_patches": len(snap.commit_patches),
        "has_repo": (dest / "repo").is_dir(),
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Materialize a container-ready snapshot payload.")
    ap.add_argument("--thread-id", required=True)
    ap.add_argument("--dest", type=Path, required=True)
    ap.add_argument("--groups", default=",".join(ALL_GROUPS),
                    help=f"comma list; default all ({','.join(ALL_GROUPS)})")
    ap.add_argument("--log-commits", type=int, default=DEFAULT_LOG_COMMITS)
    ap.add_argument("--patch-commits", type=int, default=DEFAULT_PATCH_COMMITS)
    args = ap.parse_args(argv)

    groups = {g.strip() for g in args.groups.split(",") if g.strip()}
    bad = groups - set(ALL_GROUPS)
    if bad:
        raise SystemExit(f"unknown groups: {sorted(bad)}; valid: {ALL_GROUPS}")

    meta = materialize_payload(args.thread_id, groups, args.dest,
                               args.log_commits, args.patch_commits)
    import json
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
