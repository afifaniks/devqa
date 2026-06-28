"""
Inspect a time-capped snapshot for one benchmark thread — what the snapshot_agent
actually sees at report time T.

    python -m harness.inspect_snapshot <thread_id>
    python -m harness.inspect_snapshot <thread_id> --groups advisory,issues
    python -m harness.inspect_snapshot <thread_id> --full      # no truncation
    python -m harness.inspect_snapshot --list                  # show available ids

thread_id form: owner/repo/issue/<number>  (e.g. ImageMagick/ImageMagick/issue/8584)
"""

from __future__ import annotations

import argparse
import json

from harness.snapshot import (BENCHMARK, build_snapshot, thread_meta)
from harness.tools import ALL_GROUPS


def _hr(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def _cap(s: str, n: int, full: bool) -> str:
    s = (s or "").replace("\n", " ").strip()
    return s if full or len(s) <= n else s[:n] + " …"


def list_threads() -> None:
    with open(BENCHMARK, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            hf = {k: v for k, v in (r.get("hard_facts") or {}).items() if v}
            print(f"{r['id']}\n    {r.get('title', '')[:80]}"
                  f"\n    created={r.get('created_at')}  hard_facts={hf or '{}'}")


def inspect(thread_id: str, groups: set[str], full: bool) -> None:
    from harness.snapshot import window_start
    meta = thread_meta(thread_id)
    _hr(f"THREAD  {thread_id}")
    print(f"repo         {meta['repo']}")
    print(f"report_time  {meta['created_at']}  (= T, the time cap)")
    print(f"window_start {window_start(meta['created_at'])}  (trailing 2yr floor)")
    print(f"source issue {meta.get('number')}  (EXCLUDED from snapshot)")
    hf = {k: v for k, v in (meta.get('hard_facts') or {}).items() if v}
    print(f"hard_facts   {hf or '{}'}")
    print(f"groups       {sorted(groups)}")

    snap = build_snapshot(thread_id, groups)
    # newest first
    snap.issues.sort(key=lambda d: d.get("created_at") or "", reverse=True)
    snap.prs.sort(key=lambda d: d.get("created_at") or "", reverse=True)
    snap.advisories.sort(key=lambda a: a.get("published") or "", reverse=True)

    _hr("REPO @ commit-before-T")
    if snap.worktree:
        print(f"commit  {snap.commit_sha}")
        print(f"worktree {snap.worktree}")
        try:
            tops = sorted(p.name for p in snap.worktree.iterdir())
            print(f"top-level ({len(tops)} entries): {', '.join(tops[:40])}")
        except OSError as e:
            print(f"(cannot list worktree: {e})")
    else:
        print("(code/commits group not provided)")

    _hr(f"ISSUES <= T  ({len(snap.issues)})")
    for d in snap.issues[:15]:
        print(f"  #{d['number']}  [{d.get('state')}]  {_cap(d['title'], 70, full)}"
              f"  ({len(d.get('comments') or [])} comments)")
    if len(snap.issues) > 15 and not full:
        print(f"  … +{len(snap.issues) - 15} more")

    _hr(f"PRs <= T  ({len(snap.prs)})")
    for d in snap.prs[:15]:
        print(f"  #{d['number']}  [{d.get('outcome')}]  {_cap(d['title'], 70, full)}")
    if len(snap.prs) > 15 and not full:
        print(f"  … +{len(snap.prs) - 15} more")

    _hr(f"ADVISORIES <= T  ({len(snap.advisories)})")
    for a in snap.advisories[:25]:
        print(f"  {a['id']}  aliases={a['aliases']}  cwe={a.get('cwe_ids') or []}"
              f"  [{a['severity']}]  pub={str(a['published'])[:10]}")
        print(f"      {_cap(a['summary'], 100, full)}")
    if len(snap.advisories) > 25 and not full:
        print(f"  … +{len(snap.advisories) - 25} more")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("thread_id", nargs="?", help="owner/repo/issue/<number>")
    ap.add_argument("--groups", default=",".join(ALL_GROUPS),
                    help=f"comma list, subset of {ALL_GROUPS} (default: all)")
    ap.add_argument("--full", action="store_true", help="no truncation")
    ap.add_argument("--list", action="store_true", help="list thread ids and exit")
    args = ap.parse_args()

    if args.list:
        list_threads()
        return
    if not args.thread_id:
        ap.error("thread_id required (or use --list)")

    groups = {g.strip() for g in args.groups.split(",") if g.strip()}
    bad = groups - set(ALL_GROUPS)
    if bad:
        ap.error(f"unknown groups {bad}; valid: {ALL_GROUPS}")
    inspect(args.thread_id, groups, args.full)


if __name__ == "__main__":
    main()
