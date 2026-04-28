"""
Commits miner — covers questions:
  Q8-10  (evolution of code, why changes were made)
  Q11-15 (what classes changed, who changed them)
  Q17-19 (who created/owns an API or file)
  Q21-23 (what/which classes changed most)
  Q25    (recently changed code)
  Q32-35 (broken builds — which change caused it)
  Q43    (who changed a defect)
  Q56    (which commit introduced a regression — SZZ)
"""

import re
import sys
import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from tqdm import tqdm

sys.path.insert(0, "..")
from utils.github_client import paginate, get
from utils.storage import save_jsonl, load_jsonl, already_mined
from config import REPOS, SZZ_WINDOW_DAYS


# Patterns that link a commit to an issue (closing keywords)
CLOSING_PATTERNS = [
    re.compile(r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)", re.IGNORECASE),
    re.compile(r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+https?://github\.com/[^/]+/[^/]+/issues/(\d+)", re.IGNORECASE),
]


def parse_issue_refs(message: str) -> list:
    """Extract issue numbers referenced with closing keywords in a commit message."""
    refs = []
    for pattern in CLOSING_PATTERNS:
        refs.extend(pattern.findall(message or ""))
    return [int(r) for r in refs]


def mine_commits(repo: str):
    if already_mined(repo, "commits"):
        print(f"  [skip] commits already mined for {repo}")
        return

    print(f"\n[commits] mining {repo} ...")

    records = []
    # Track file-level stats for ownership questions (Q18, Q19, Q23)
    file_commit_counts = defaultdict(int)
    file_authors = defaultdict(set)

    for commit in tqdm(paginate(f"/repos/{repo}/commits"), desc="  fetching commits"):
        sha = commit["sha"]

        # Fetch full commit detail (includes files changed)
        try:
            detail = get(f"/repos/{repo}/commits/{sha}")
        except Exception as e:
            print(f"  [warn] could not fetch commit {sha}: {e}")
            continue

        message = detail["commit"]["message"]
        author = detail["commit"]["author"]
        files = detail.get("files", [])

        file_paths = [f["filename"] for f in files]
        additions = sum(f.get("additions", 0) for f in files)
        deletions = sum(f.get("deletions", 0) for f in files)

        # Update file ownership counters
        for fp in file_paths:
            file_commit_counts[fp] += 1
            if detail.get("author"):
                file_authors[fp].add(detail["author"]["login"])

        # Parse issue references — these link commits to bugs (needed for SZZ)
        issue_refs = parse_issue_refs(message)

        record = {
            "repo": repo,
            "sha": sha,
            "message": message,
            "author_name": author.get("name"),
            "author_email": author.get("email"),
            "author_login": detail["author"]["login"] if detail.get("author") else None,
            "committed_at": author.get("date"),
            "files_changed": file_paths,
            "additions": additions,
            "deletions": deletions,
            "parents": [p["sha"] for p in detail.get("parents", [])],

            # Q56 ground truth linkage: commit → issue
            "closes_issues": issue_refs,

            # Useful for Q9/Q10: is this commit a bug fix?
            "is_bug_fix": len(issue_refs) > 0 or any(
                kw in message.lower()
                for kw in ["fix", "bug", "patch", "regression", "crash", "error"]
            ),
        }
        records.append(record)

    save_jsonl(repo, "commits", records)

    # Save file ownership summary separately (used for Q18, Q19, Q23)
    ownership = []
    for filepath, count in file_commit_counts.items():
        ownership.append({
            "repo": repo,
            "filepath": filepath,
            "total_commits": count,
            "unique_authors": list(file_authors[filepath]),
        })
    save_jsonl(repo, "file_ownership", ownership)

    print(f"  done — {len(records)} commits, {len(ownership)} files tracked")


def run_szz(repo: str):
    """
    Simplified SZZ: for each bug-fixing commit, find the most recent commit
    that last touched the same files within the SZZ_WINDOW_DAYS window.
    Produces (fix_commit, inducing_commit, issue_number) triples.

    Ground truth for Q56: which commit introduced a regression?
    """
    if already_mined(repo, "szz_pairs"):
        print(f"  [skip] SZZ already run for {repo}")
        return

    print(f"\n[SZZ] running for {repo} ...")
    commits = load_jsonl(repo, "commits")
    if not commits:
        print("  [warn] no commits found — run mine_commits first")
        return

    # Index commits by sha and build a chronological list
    by_sha = {c["sha"]: c for c in commits}
    sorted_commits = sorted(commits, key=lambda c: c.get("committed_at", ""))

    # Build index: file → list of (committed_at, sha, author) sorted by time
    file_timeline = defaultdict(list)
    for c in sorted_commits:
        for fp in c.get("files_changed", []):
            file_timeline[fp].append((c["committed_at"], c["sha"], c.get("author_login")))

    window = timedelta(days=SZZ_WINDOW_DAYS)
    pairs = []

    bug_fix_commits = [c for c in sorted_commits if c.get("is_bug_fix") and c.get("closes_issues")]

    for fix in tqdm(bug_fix_commits, desc="  finding inducing commits"):
        fix_time_str = fix.get("committed_at")
        if not fix_time_str:
            continue
        fix_time = datetime.fromisoformat(fix_time_str.replace("Z", "+00:00"))

        for fp in fix.get("files_changed", []):
            timeline = file_timeline.get(fp, [])
            # Find the most recent commit touching this file BEFORE the fix
            candidates = [
                (t, sha, author)
                for (t, sha, author) in timeline
                if t < fix_time_str and sha != fix["sha"]
            ]
            if not candidates:
                continue
            # Take the most recent candidate within the window
            candidates_in_window = [
                (t, sha, author) for (t, sha, author) in candidates
                if fix_time - datetime.fromisoformat(t.replace("Z", "+00:00")) <= window
            ]
            if not candidates_in_window:
                continue
            inducing_time, inducing_sha, inducing_author = max(candidates_in_window, key=lambda x: x[0])

            for issue_num in fix.get("closes_issues", []):
                pairs.append({
                    "repo": repo,
                    "issue_number": issue_num,
                    "fix_sha": fix["sha"],
                    "fix_author": fix.get("author_login"),
                    "fix_at": fix.get("committed_at"),
                    "inducing_sha": inducing_sha,
                    "inducing_author": inducing_author,
                    "inducing_at": inducing_time,
                    "file": fp,

                    # Q56 ground truth: given issue X, the inducing commit is `inducing_sha`
                    "ground_truth_q56": {
                        "question": f"Which commit introduced the regression in issue #{issue_num}?",
                        "answer_sha": inducing_sha,
                        "answer_author": inducing_author,
                        "file": fp,
                    }
                })

    save_jsonl(repo, "szz_pairs", pairs)
    print(f"  done — {len(pairs)} (fix, inducing) commit pairs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=None)
    parser.add_argument("--skip-szz", action="store_true")
    args = parser.parse_args()
    repos = [args.repo] if args.repo else REPOS
    for repo in repos:
        mine_commits(repo)
        if not args.skip_szz:
            run_szz(repo)
