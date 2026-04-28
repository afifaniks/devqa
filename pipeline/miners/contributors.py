"""
Contributors miner — covers questions:
  Q1-6   (who is working on what, how much work)
  Q20    (who to talk to about unfamiliar packages)
  Q42    (how is the team organized)
  Q45    (collaboration tree around a feature)
  Q54    (who should own this bug — expertise signal)
  Q74    (who has most context on a bug)
"""

import sys
import argparse
from collections import defaultdict
from tqdm import tqdm

sys.path.insert(0, "..")
from utils.github_client import paginate, get
from utils.storage import save_jsonl, load_jsonl, already_mined
from config import REPOS


def mine_contributors(repo: str):
    if already_mined(repo, "contributors"):
        print(f"  [skip] contributors already mined for {repo}")
        return

    print(f"\n[contributors] mining {repo} ...")

    # ── 1. Commit activity per contributor ──────────────────────────────────
    commit_counts = defaultdict(int)
    file_expertise = defaultdict(lambda: defaultdict(int))  # author → file → commit count

    for commit in tqdm(load_jsonl(repo, "commits"), desc="  building expertise from commits"):
        author = commit.get("author_login")
        if not author:
            continue
        commit_counts[author] += 1
        for fp in commit.get("files_changed", []):
            # Track expertise at directory level too (for Q20)
            file_expertise[author][fp] += 1
            parts = fp.split("/")
            for depth in range(1, len(parts)):
                dir_path = "/".join(parts[:depth])
                file_expertise[author][dir_path] += 1

    # ── 2. Issue activity per contributor ───────────────────────────────────
    issue_comments = defaultdict(int)    # author → comment count on issues
    issues_reported = defaultdict(int)
    issues_assigned = defaultdict(int)

    for issue in tqdm(load_jsonl(repo, "issues"), desc="  building expertise from issues"):
        reporter = issue.get("reporter")
        if reporter:
            issues_reported[reporter] += 1
        for assignee in issue.get("assignees", []):
            issues_assigned[assignee] += 1
        for comment in issue.get("comments", []):
            author = comment.get("author")
            if author:
                issue_comments[author] += 1

    # ── 3. PR review activity ───────────────────────────────────────────────
    review_counts = defaultdict(int)
    reviews_received = defaultdict(int)

    for pr in tqdm(load_jsonl(repo, "pull_requests"), desc="  building expertise from PRs"):
        pr_author = pr.get("author")
        for review in pr.get("reviews", []):
            reviewer = review.get("reviewer")
            if reviewer:
                review_counts[reviewer] += 1
            if pr_author:
                reviews_received[pr_author] += 1

    # ── 4. Build per-contributor profile ────────────────────────────────────
    all_authors = set(commit_counts) | set(issue_comments) | set(review_counts)
    profiles = []

    for author in tqdm(all_authors, desc="  building profiles"):
        # Top files this contributor has worked on (expertise signal for Q20, Q54, Q74)
        top_files = sorted(
            file_expertise[author].items(),
            key=lambda x: -x[1]
        )[:20]

        # Top directories (package-level expertise for Q20)
        top_dirs = [
            (fp, count) for fp, count in top_files
            if "/" not in fp or fp.count("/") < 2
        ]

        profiles.append({
            "repo": repo,
            "login": author,
            "total_commits": commit_counts[author],
            "total_issue_comments": issue_comments[author],
            "total_reviews_given": review_counts[author],
            "total_reviews_received": reviews_received[author],
            "issues_reported": issues_reported[author],
            "issues_assigned": issues_assigned[author],

            # Q20/Q54/Q74 ground truth signal: what files/dirs does this person know?
            "top_files": [{"file": f, "commits": c} for f, c in top_files],
            "top_directories": [{"dir": d, "commits": c} for d, c in top_dirs],

            # Simple activity score (useful for ranking in assignment questions)
            "activity_score": (
                commit_counts[author] * 3
                + review_counts[author] * 2
                + issue_comments[author]
            ),
        })

    save_jsonl(repo, "contributors", profiles)

    # ── 5. Build file → expert mapping (Q18, Q19, Q20 ground truth) ─────────
    file_experts = defaultdict(list)
    for profile in profiles:
        for entry in profile["top_files"]:
            file_experts[entry["file"]].append({
                "login": profile["login"],
                "commits": entry["commits"],
            })

    file_expert_records = [
        {
            "repo": repo,
            "file": fp,
            "experts": sorted(experts, key=lambda x: -x["commits"])[:5],
            # Q18 ground truth: most recent modifier is in commits.jsonl
            # Q19 ground truth: most frequent modifier = experts[0]
        }
        for fp, experts in file_experts.items()
    ]
    save_jsonl(repo, "file_experts", file_expert_records)

    print(f"  done — {len(profiles)} contributor profiles, {len(file_expert_records)} file expert mappings")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=None)
    args = parser.parse_args()
    repos = [args.repo] if args.repo else REPOS
    for repo in repos:
        mine_contributors(repo)
