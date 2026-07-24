"""
SecDevQA — host-side materialization of a container-ready snapshot payload.

The container is offline (egress is allowlisted to the model API and the vuln-resolution hosts
only), so everything an agent may need from the repository must be baked into the payload here,
on the host, where the cached clone and network are available. This module turns a
:class:`~harness.snapshot.builder.Snapshot` into a directory the container mounts read-only and
the in-container MCP server (:mod:`harness.mcp.server`) reconstructs verbatim.

What it produces (only the enabled artifact groups are materialized):

  code     ``repo.git/`` — a BARE MIRROR holding ``commit_sha`` and its ancestors only, fetched
           by SHA (never by branch tip, which would drag in post-report commits). The container's
           entrypoint clones it to a working tree and checks out ``commit_sha``, so the agent gets
           a REAL repository: ``git log``/``blame``/``diff``/``show`` work natively and
           ``git rev-parse HEAD`` is genuinely the base commit. Airtight by construction rather
           than by a guard — nothing committed after the report exists in the object store, so
           even ``git log --all`` cannot reach the thread's fix. Offline-complete: the clone is a
           local path, so the container needs no network.

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
import time
from pathlib import Path

from harness.snapshot.builder import Snapshot, build_snapshot, thread_meta
from harness.snapshot.payload import dump_snapshot
from harness.snapshot.tools import ALL_GROUPS

# Bounds for the precomputed `commits` history. Log entries are commit metadata (free from a
# blobless clone); patches require blobs (lazy-fetched on the host at build time), so their
# window is smaller to bound network/time. Both cover the recent history an agent at time T
# would plausibly inspect; older commits fall back to a graceful "not available offline".
DEFAULT_LOG_COMMITS = 200
DEFAULT_PATCH_COMMITS = 40

# Depth of the container's repo mirror. History beyond this is grafted away; the checked-out
# tree is always complete. Matches DEFAULT_LOG_COMMITS so native `git log` reaches as far back
# as the precomputed log used to.
DEFAULT_MIRROR_DEPTH = 200

# Bare mirror inside the payload; the container clones from it at <payload>/repo.git.
MIRROR_SUBDIR = "repo.git"

# Deterministic identity for the synthetic snapshot commit (never depends on user git config).
_GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "SecDevQA", "GIT_AUTHOR_EMAIL": "snapshot@secdevqa.local",
    "GIT_COMMITTER_NAME": "SecDevQA", "GIT_COMMITTER_EMAIL": "snapshot@secdevqa.local",
}


def _run(cmd: list[str], cwd: Path, env: dict | None = None,
         stdin: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True,
                          env=env, check=True)


def _build_snapshot_mirror(repo: str, commit_sha: str, branch: str, mirror_dest: Path,
                           depth: int = DEFAULT_MIRROR_DEPTH) -> int:
    """Build a bare git mirror at `mirror_dest` containing ONLY `commit_sha` and its ancestors.

    The container clones from this mirror and checks out `commit_sha`, so the agent gets a REAL
    repository — native ``git log``/``blame``/``diff``/``show`` all work, and
    ``git rev-parse HEAD`` is genuinely the base commit.

    Airtightness is structural rather than enforced by a guard: fetching a single commit brings
    down that commit's ancestry and nothing else, so no post-report commit exists anywhere in the
    object store. ``git log --all`` cannot reveal the thread's fix. The single ref we then create
    points at `commit_sha`, so there is no branch tip ahead of it either.

    `depth` bounds the fetch (history beyond it is grafted away), keeping mirrors small; blobs for
    the checked-out tree and the recent window come with it, so the container needs no network.

    Returns the number of release tags carried over (see :func:`_add_ancestor_tags`)."""
    mirror_dest.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, **_GIT_IDENTITY}
    _run(["git", "init", "--bare", "-q"], cwd=mirror_dest, env=env)
    # GitHub permits fetching a reachable SHA directly, so we never pull a branch tip (which
    # would drag in commits made after the report).
    _run(["git", "fetch", "--depth", str(depth), "--no-tags",
          f"https://github.com/{repo}.git", commit_sha], cwd=mirror_dest, env=env)
    ref = f"refs/heads/{branch or 'main'}"
    _run(["git", "update-ref", ref, commit_sha], cwd=mirror_dest, env=env)
    _run(["git", "symbolic-ref", "HEAD", ref], cwd=mirror_dest, env=env)
    return _add_ancestor_tags(mirror_dest, repo)


def _add_ancestor_tags(mirror: Path, repo: str) -> int:
    """Create tag refs for releases that existed at the snapshot, and only those.

    Release questions ("which version fixes this?") are a large slice of the benchmark, and
    agents reach for them with ``git tag``/``git describe``/``git tag --contains`` — which
    return nothing without tag refs.

    Leak-safe by construction: ``ls-remote`` transfers no objects, and a tag ref is created
    ONLY when the mirror already contains its target commit. Since the mirror holds nothing
    but ancestors of the base commit, a tag on any later commit — including the release that
    carries a thread's fix — simply cannot be created. No object is ever fetched here.
    """
    out = _git_out(mirror, "ls-remote", "--tags", f"https://github.com/{repo}.git")
    wanted: dict[str, str] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) != 2 or not parts[1].startswith("refs/tags/"):
            continue
        sha, name = parts[0], parts[1][len("refs/tags/"):]
        peeled = name.endswith("^{}")            # annotated tag → its commit
        if peeled:
            name = name[:-3]
        if peeled or name not in wanted:         # peeled entry wins
            wanted[name] = sha

    n = 0
    for name, sha in wanted.items():
        have = subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"],
                              cwd=mirror, capture_output=True)
        if have.returncode != 0:
            continue                             # target not an ancestor → post-snapshot
        made = subprocess.run(["git", "update-ref", f"refs/tags/{name}", sha],
                              cwd=mirror, capture_output=True)
        n += made.returncode == 0
    return n


def _mirror_info(mirror: Path, commit_sha: str) -> dict:
    """Size / commit-count / base-commit date, for the run log."""
    n = _git_out(mirror, "rev-list", "--count", commit_sha).strip()
    when = _git_out(mirror, "show", "-s", "--format=%cI", commit_sha).strip()
    size = sum(f.stat().st_size for f in mirror.rglob("*") if f.is_file())
    return {"n_commits": n or "?", "committed_at": when or "?",
            "size_mb": size / (1024 * 1024)}


def _git_out(clone: Path, *args: str) -> str:
    # errors="replace": commit patches/logs are not guaranteed UTF-8 (binary diffs, latin-1
    # filenames or author names) — strict decoding would raise mid-materialization.
    r = subprocess.run(["git", *args], cwd=clone, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
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
    meta_row = thread_meta(thread_id)
    base = meta_row.get("base_commit") or {}
    branch = base.get("branch") or "main"

    # The recorded base_commit is the authoritative snapshot base; a disagreement means the
    # cached clone drifted (stale clone, force-push, rewritten history) and would silently hand
    # the agent the wrong tree, so fail loudly instead.
    if base.get("sha") and snap.commit_sha and base["sha"] != snap.commit_sha:
        raise RuntimeError(
            f"snapshot base mismatch for {thread_id}: benchmark base_commit={base['sha'][:12]} "
            f"but clone resolved {snap.commit_sha[:12]} at T={snap.report_time}. "
            f"The cached clone is stale or history was rewritten — refresh "
            f"harness/cache/repos/ and retry.")
    commit_sha = base.get("sha") or snap.commit_sha

    if "code" in groups and commit_sha:
        t0 = time.time()
        print(f"  [snapshot] mirroring {snap.repo} @ {commit_sha[:12]} "
              f"(branch {branch}, depth {DEFAULT_MIRROR_DEPTH}) ...", flush=True)
        n_tags = _build_snapshot_mirror(snap.repo, commit_sha, branch, dest / MIRROR_SUBDIR)
        info = _mirror_info(dest / MIRROR_SUBDIR, commit_sha)
        print(f"  [snapshot] mirror ready in {time.time() - t0:.1f}s — "
              f"{info['n_commits']} commits, {n_tags} tags, {info['size_mb']:.1f} MB, "
              f"base committed {info['committed_at']}", flush=True)

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
        "commit_sha": commit_sha,
        "base_commit_verified": bool(base.get("sha")),
        "branch": branch,
        "groups": sorted(groups),
        "n_issues": len(snap.issues),
        "n_prs": len(snap.prs),
        "n_advisories": len(snap.advisories),
        "n_commit_patches": len(snap.commit_patches),
        "has_repo": (dest / MIRROR_SUBDIR).is_dir(),
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
