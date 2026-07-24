#!/usr/bin/env python
"""
extract_fixes.py — fetch fix commits/PRs for each benchmark thread, capture their
diffs, and classify each thread as fix_before / fix_after / explanation_only by
comparing the fix's landing time to the report time (issue open date, t_theta).

Adds THREE new fields to every record in security_benchmark_final.jsonl:

  fix_artifacts   list[dict]  — one entry per fetched fix commit/PR:
                  {type, id, url, fix_time, fix_time_basis, author_date,
                   committer_date | merged_at, merged, files:[{path, patch}], flags:[]}
                  ([] when the thread cites no fix commit/PR)

  resolution_case str  — one of:
                  "fix_before"      a fix landed BEFORE t_theta (retrievable from the snapshot)
                  "fix_after"       the fix landed AFTER t_theta (future fact at query time)
                  "explanation_only" the thread cites no fix commit/PR
                  "undetermined"    fix cited but no usable timestamp (unmerged PR / 404) — human-check

  base_commit     dict | None — repo state at report time (snapshot base):
                  {sha, branch, committed_at, url, flags} — last default-branch commit
                  at/before t_theta.

Usage (run in the devqa env, with GITHUB_TOKEN[S] in .env):
  /local/home/amamun/envs/devqa/bin/python dataset/extract_fixes.py            # in place (+ .bak)
  /local/home/amamun/envs/devqa/bin/python dataset/extract_fixes.py --limit 5  # smoke test
  /local/home/amamun/envs/devqa/bin/python dataset/extract_fixes.py --force    # ignore cache
  /local/home/amamun/envs/devqa/bin/python dataset/extract_fixes.py --output dataset/_with_fixes.jsonl
"""

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()  # project-root .env: GITHUB_TOKENS / GITHUB_TOKEN

BASE = "https://api.github.com"
PATCH_CHAR_CAP = 20_000  # truncate any single file patch beyond this (note in flags)
_RL_THRESHOLD = 50


# --------------------------------------------------------------------------- #
# GitHub REST with token rotation + rate-limit handling                       #
# --------------------------------------------------------------------------- #
class GitHub:
    def __init__(self, cache_dir, force=False):
        toks = [t.strip() for t in os.getenv("GITHUB_TOKENS", "").split(",") if t.strip()]
        if not toks and os.getenv("GITHUB_TOKEN"):
            toks = [os.getenv("GITHUB_TOKEN")]
        if not toks:
            raise SystemExit("No GitHub token: set GITHUB_TOKENS or GITHUB_TOKEN in .env")
        self.sessions = []
        for t in toks:
            s = requests.Session()
            s.headers.update({
                "Authorization": f"token {t}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            })
            self.sessions.append(s)
        self.idx = 0
        self.remaining = [10_000] * len(toks)
        self.reset_at = [0] * len(toks)
        self.cache_dir = cache_dir
        self.force = force
        os.makedirs(cache_dir, exist_ok=True)

    def _cache_path(self, key):
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", key)
        return os.path.join(self.cache_dir, safe + ".json")

    def _rotate_if_needed(self, resp):
        self.remaining[self.idx] = int(resp.headers.get("X-RateLimit-Remaining", 100))
        self.reset_at[self.idx] = int(resp.headers.get("X-RateLimit-Reset", 0))
        if self.remaining[self.idx] >= _RL_THRESHOLD:
            return
        for off in range(1, len(self.sessions)):
            cand = (self.idx + off) % len(self.sessions)
            if self.remaining[cand] >= _RL_THRESHOLD:
                self.idx = cand
                return
        wait = max(min(self.reset_at) - time.time() + 5, 0)
        if wait:
            print(f"  [rate limit] sleeping {int(wait)}s")
            time.sleep(wait)

    def get(self, path, params=None, paginate=False):
        """GET BASE+path. Cached by (path, params). Returns parsed JSON, or None on 404."""
        key = path + ("?" + json.dumps(params, sort_keys=True) if params else "") + ("|all" if paginate else "")
        cp = self._cache_path(key)
        if not self.force and os.path.exists(cp):
            with open(cp) as f:
                return json.load(f)

        out = []
        url = BASE + path
        p = dict(params or {})
        if paginate:
            p["per_page"] = 100
        result = None
        while True:
            for attempt in range(4):
                try:
                    resp = self.sessions[self.idx].get(url, params=p, timeout=30)
                    break
                except requests.RequestException as e:
                    if attempt == 3:
                        raise
                    time.sleep(2 * (attempt + 1))
            self._rotate_if_needed(resp)
            if resp.status_code in (404, 422):
                # 404 = missing; 422 = unprocessable ref (bad/ambiguous/cross-repo short SHA).
                # Either way the artifact isn't resolvable here — treat as not-found, don't crash.
                result = None
                break
            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                self._rotate_if_needed(resp)
                continue
            resp.raise_for_status()
            data = resp.json()
            if not paginate:
                result = data
                break
            out.extend(data)
            nxt = resp.links.get("next")
            if not nxt:
                result = out
                break
            url, p = nxt["url"], {}

        with open(cp, "w") as f:
            json.dump(result, f)
        return result


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def parse_dt(s):
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def cap_patch(patch, flags):
    if patch and len(patch) > PATCH_CHAR_CAP:
        flags.append("patch_truncated")
        return patch[:PATCH_CHAR_CAP] + "\n... [truncated] ..."
    return patch


def fetch_commit(gh, repo, sha, via="hard_facts"):
    data = gh.get(f"/repos/{repo}/commits/{sha}")
    flags = []
    if data is None:
        return {"type": "commit", "repo": repo, "id": sha, "via": via, "url": None,
                "fix_time": None, "fix_time_basis": None, "flags": ["not_found"], "files": []}
    commit = data.get("commit", {})
    author_date = (commit.get("author") or {}).get("date")
    committer_date = (commit.get("committer") or {}).get("date")
    if author_date and committer_date and author_date != committer_date:
        flags.append("author!=committer_date(possible_rebase)")
    files = [{"path": f.get("filename"), "patch": cap_patch(f.get("patch"), flags)}
             for f in (data.get("files") or [])]
    return {
        "type": "commit", "repo": repo, "id": sha, "via": via, "url": data.get("html_url"),
        "fix_time": committer_date, "fix_time_basis": "committer_date",
        "author_date": author_date, "committer_date": committer_date,
        "files": files, "flags": flags,
    }


def fetch_pr(gh, repo, num, via="hard_facts"):
    pr = gh.get(f"/repos/{repo}/pulls/{num}")
    flags = []
    if pr is None:
        # '#num' might reference an issue or a PR in another context; flag for human check
        return {"type": "pr", "repo": repo, "id": f"#{num}", "via": via, "url": None,
                "fix_time": None, "fix_time_basis": None,
                "flags": ["not_found_or_not_a_pr"], "files": []}
    merged_at = pr.get("merged_at")
    if merged_at:
        fix_time, basis = merged_at, "merged_at"
    else:
        fix_time, basis = pr.get("created_at"), "pr_created_at(unmerged)"
        flags.append("pr_not_merged")
    pr_files = gh.get(f"/repos/{repo}/pulls/{num}/files", paginate=True) or []
    files = [{"path": f.get("filename"), "patch": cap_patch(f.get("patch"), flags)}
             for f in pr_files]
    return {
        "type": "pr", "repo": repo, "id": f"#{num}", "via": via, "url": pr.get("html_url"),
        "fix_time": fix_time, "fix_time_basis": basis,
        "merged": bool(merged_at), "merged_at": merged_at, "created_at": pr.get("created_at"),
        "files": files, "flags": flags,
    }


def fetch_base_commit(gh, repo, t_theta):
    """Last commit on the default branch AT/BEFORE the report time t_theta.

    This is the snapshot base — the repo state a system sees when the issue was opened
    (mirrors harness/snapshot.py's 'commit-before-report'). Returns
    {sha, committed_at, branch, url} or None.
    """
    if t_theta is None:
        return None
    repo_meta = gh.get(f"/repos/{repo}")
    branch = (repo_meta or {}).get("default_branch") or "main"
    # GitHub lists commits in reverse-chronological order; `until` caps at t_theta.
    until = t_theta.strftime("%Y-%m-%dT%H:%M:%SZ")
    commits = gh.get(f"/repos/{repo}/commits",
                     params={"sha": branch, "until": until, "per_page": 1})
    if not commits:
        return {"sha": None, "branch": branch, "committed_at": None, "url": None,
                "flags": ["no_commit_before_report"]}
    c = commits[0]
    return {
        "sha": c.get("sha"),
        "branch": branch,
        "committed_at": (c.get("commit", {}).get("committer") or {}).get("date"),
        "url": c.get("html_url"),
        "flags": [],
    }


# --------------------------------------------------------------------------- #
# Harvest fix references from the answer text (not just hard_facts).           #
# Manually-assigned gold answers like "Patch commit: <url>" carry the fix as a #
# link in the answer/grounding, not in hard_facts — collect those too.         #
# --------------------------------------------------------------------------- #
_COMMIT_URL = re.compile(r"github\.com/([\w.-]+/[\w.-]+)/commit/([0-9a-fA-F]{7,40})")
_PULL_URL = re.compile(r"github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)")
# bare '#123' only when clearly a PR ('PR #123' / 'pull request #123')
_BARE_PR = re.compile(r"(?:\bPR\b|pull request)\s*#?(\d{2,6})", re.I)


def collect_refs(record):
    """Return deduped fix refs from hard_facts ∪ answer text.

    Each ref: {repo, kind: 'commit'|'pr', id, via: 'hard_facts'|'answer'}.
    'answer' sources: each qa_pair.answer + grounding_sources, plus the answer comment body.
    """
    repo = record["repo"]
    seen, refs = set(), []

    def add(rp, kind, rid, via):
        key = (rp.lower(), kind, str(rid).lower())
        if key not in seen:
            seen.add(key)
            refs.append({"repo": rp, "kind": kind, "id": str(rid), "via": via})

    hf = record.get("hard_facts") or {}
    for sha in hf.get("fix_commits") or []:
        add(repo, "commit", sha, "hard_facts")
    for pr in hf.get("fix_prs") or []:
        num = re.sub(r"\D", "", str(pr))
        if num:
            add(repo, "pr", num, "hard_facts")

    # text sources: normalized answers + grounding, and the raw answer comment
    texts = []
    for qa in record.get("qa_pairs") or []:
        texts.append(qa.get("answer") or "")
        texts.extend(qa.get("grounding_sources") or [])
    aid = record.get("answer_comment_id")
    for c in record.get("comments") or []:
        if c.get("id") == aid:
            texts.append(c.get("body") or "")
    blob = "\n".join(texts)
    for rp, sha in _COMMIT_URL.findall(blob):
        add(rp, "commit", sha, "answer")
    for rp, num in _PULL_URL.findall(blob):
        add(rp, "pr", num, "answer")
    for num in _BARE_PR.findall(blob):
        add(repo, "pr", num, "answer")
    return refs


def classify(artifacts, t_theta):
    """Earliest usable fix time vs report time → resolution_case."""
    times = [parse_dt(a["fix_time"]) for a in artifacts if a.get("fix_time")]
    times = [t for t in times if t]
    if not artifacts:
        return "explanation_only"
    if not times:
        return "undetermined"          # fix cited but unmerged/404 — needs human check
    earliest = min(times)
    return "fix_before" if earliest < t_theta else "fix_after"


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="dataset/security_benchmark_final.jsonl")
    ap.add_argument("--output", default=None,
                    help="write here instead of in place (no .bak written)")
    ap.add_argument("--cache-dir", default="dataset/.fix_cache")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--force", action="store_true", help="ignore cached API responses")
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.input) if l.strip()]
    gh = GitHub(args.cache_dir, force=args.force)

    summary = {}
    n = len(rows) if args.limit is None else min(args.limit, len(rows))
    for i, r in enumerate(rows[:n]):
        repo = r["repo"]
        t_theta = parse_dt(r.get("created_at"))
        refs = collect_refs(r)
        artifacts = []
        for ref in refs:
            if ref["kind"] == "commit":
                artifacts.append(fetch_commit(gh, ref["repo"], ref["id"], via=ref["via"]))
            else:
                artifacts.append(fetch_pr(gh, ref["repo"], ref["id"], via=ref["via"]))

        case = classify(artifacts, t_theta)
        r["fix_artifacts"] = artifacts
        r["answer_references"] = [a for a in refs if a["via"] == "answer"]
        r["resolution_case"] = case
        r["base_commit"] = fetch_base_commit(gh, repo, t_theta)
        summary[case] = summary.get(case, 0) + 1
        flagged = [f for a in artifacts for f in a.get("flags", [])]
        base_sha = (r["base_commit"] or {}).get("sha")
        base_short = base_sha[:9] if base_sha else "none"
        print(f"[{i + 1}/{n}] {r['id']:50s} {case:16s} "
              f"artifacts={len(artifacts)} base={base_short} "
              f"{('FLAGS:' + ','.join(flagged)) if flagged else ''}")

    # write out
    if args.output:
        out_path = args.output
    else:
        out_path = args.input
        bak = args.input + ".bak"
        if not os.path.exists(bak):          # back up the TRUE original once
            import shutil
            shutil.copyfile(args.input, bak)
            print(f"backup → {bak}")

    tmp = out_path + ".tmp"
    with open(tmp, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    os.replace(tmp, out_path)

    print(f"\nwrote {len(rows)} records → {out_path}")
    print("resolution_case (processed {} of {}): {}".format(n, len(rows), summary))
    undet = [r["id"] for r in rows[:n] if r.get("resolution_case") == "undetermined"]
    if undet:
        print("UNDETERMINED (human-check):")
        for x in undet:
            print("  ", x)


if __name__ == "__main__":
    main()
