"""
SecDevQA — on-disk serialization contract for a time-capped Snapshot.

This module is the SINGLE source of truth for how a :class:`~harness.snapshot.builder.Snapshot`
is written to and read back from a directory. It is shared by two callers that must agree
byte-for-byte on the layout:

  * the host-side materializer (harness/container), which builds a snapshot with the cached
    clone/worktree/advisory machinery and writes the payload a container will mount;
  * the in-container MCP server (harness/mcp/server.py), which reconstructs the Snapshot from
    that payload — WITHOUT any git clone, network, or advisory-database access.

On-disk layout of a payload directory::

    <dir>/
      config.json          repo, report_time, excluded_issue, commit_sha, groups, worktree
      repo/                 (optional) the worktree tree, when copied into the payload
      data/issues.json      snap.issues     (list[dict], may be absent when group disabled)
      data/prs.json         snap.prs
      data/advisories.json  snap.advisories

The repository worktree is large, so it is NOT copied by default: ``config.json`` records the
absolute ``worktree`` path and the reader uses it in place. A caller that needs a relocatable,
self-contained payload (e.g. to bind-mount into a container at a fixed path) passes
``copy_repo=True`` to embed the tree at ``<dir>/repo`` instead; the reader prefers an embedded
``repo/`` when present and falls back to the recorded path otherwise.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from harness.snapshot.builder import Snapshot

CONFIG_NAME = "config.json"
REPO_SUBDIR = "repo"
DATA_SUBDIR = "data"

# Artifact-list fields written under data/, keyed by the Snapshot attribute name.
_DATA_FIELDS = ("issues", "prs", "advisories")


def dump_snapshot(snap: Snapshot, dest: Path, groups: set[str],
                  copy_repo: bool = False) -> Path:
    """Serialize `snap` (materializing the artifact `groups`) into `dest`; returns `dest`.

    `dest` is created if needed and its ``data/`` subtree is reset. The worktree is embedded
    at ``dest/repo`` when `copy_repo` is set, otherwise referenced by absolute path in
    ``config.json`` (cheaper; requires the reader to share the filesystem)."""
    dest.mkdir(parents=True, exist_ok=True)
    data_dir = dest / DATA_SUBDIR
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir()

    for field in _DATA_FIELDS:
        (data_dir / f"{field}.json").write_text(
            json.dumps(getattr(snap, field), ensure_ascii=False), encoding="utf-8")

    # Precomputed offline commit history for the `commits` group (empty on the host path).
    (data_dir / "commit_log.txt").write_text(snap.commit_log, encoding="utf-8")
    (data_dir / "commit_patches.json").write_text(
        json.dumps(snap.commit_patches, ensure_ascii=False), encoding="utf-8")

    # A repo embedded at dest/repo (either copied here or built in place by the materializer)
    # is the worktree; the reader resolves it by convention, so no absolute path is recorded.
    worktree_ref: str | None = None
    if copy_repo and snap.worktree is not None:
        repo_dest = dest / REPO_SUBDIR
        if repo_dest.exists():
            shutil.rmtree(repo_dest)
        shutil.copytree(snap.worktree, repo_dest, symlinks=True)
    elif snap.worktree is not None and not (dest / REPO_SUBDIR).is_dir():
        worktree_ref = str(snap.worktree)   # referenced in place (shared-filesystem readers)

    config = {
        "repo": snap.repo,
        "report_time": snap.report_time,
        "excluded_issue": snap.excluded_issue,
        "commit_sha": snap.commit_sha,
        "groups": sorted(groups),
        "worktree": worktree_ref,   # None when embedded at repo/ or when code group disabled
    }
    (dest / CONFIG_NAME).write_text(json.dumps(config, indent=1), encoding="utf-8")
    return dest


def load_snapshot(src: Path) -> tuple[Snapshot, set[str]]:
    """Reconstruct a (Snapshot, groups) pair from a payload directory `src`.

    The worktree resolves to an embedded ``src/repo`` when present, else the absolute path
    recorded in ``config.json`` (None when the code/commits groups were disabled). No network,
    clone, or advisory-database access is performed — every artifact is read from the payload."""
    config = json.loads((src / CONFIG_NAME).read_text(encoding="utf-8"))

    embedded = src / REPO_SUBDIR
    if embedded.is_dir():
        worktree: Path | None = embedded
    elif config.get("worktree"):
        worktree = Path(config["worktree"])
    else:
        worktree = None

    def _read(field: str) -> list[dict]:
        path = src / DATA_SUBDIR / f"{field}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    log_path = src / DATA_SUBDIR / "commit_log.txt"
    patches_path = src / DATA_SUBDIR / "commit_patches.json"

    snap = Snapshot(
        repo=config["repo"],
        report_time=config["report_time"],
        excluded_issue=config.get("excluded_issue"),
        commit_sha=config.get("commit_sha", ""),
        worktree=worktree,
        clone=None,                       # the payload never carries the clone
        issues=_read("issues"),
        prs=_read("prs"),
        advisories=_read("advisories"),
        commit_log=log_path.read_text(encoding="utf-8") if log_path.exists() else "",
        commit_patches=(json.loads(patches_path.read_text(encoding="utf-8"))
                        if patches_path.exists() else {}),
    )
    return snap, set(config.get("groups") or [])
