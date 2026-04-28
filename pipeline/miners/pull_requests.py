"""
Pull requests miner — covers questions:
  Q5     (who to assign a code review to)
  Q7     (which code reviews assigned to whom)
  Q47    (who should review this PR)
  Q48    (rationale behind merge/rejection)
  Q49    (which PRs block this issue)
  Q50    (how long does PR review take)
  Q51    (which PRs open longest without review)
  Q52    (which bugs likely fixed by this PR)
"""

import re
import sys
import argparse
from datetime import datetime
from tqdm import tqdm

sys.path.insert(0, "..")
from utils.github_client import paginate, get
from utils.storage import save_jsonl, already_mined
from config import REPOS, MIN_COMMENT_LENGTH


CLOSING_PATTERNS = [
    re.compile(r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)", re.IGNORECASE),
]


def parse_closes(text: str) -> list:
    refs = []
    for p in CLOSING_PATTERNS:
        refs.extend(p.findall(text or ""))
    return [int(r) for r in refs]


def time_to_first_review(pr_created: str, reviews: list) -> float | None:
    """Hours from PR creation to first review activity."""
    if not reviews:
        return None
    review_times = [r["submitted_at"] for r in reviews if r.get("submitted_at")]
    if not review_times:
        return None
    first = min(review_times)
    t0 = datetime.fromisoformat(pr_created.replace("Z", "+00:00"))
    t1 = datetime.fromisoformat(first.replace("Z", "+00:00"))
    return (t1 - t0).total_seconds() / 3600


def mine_pull_requests(repo: str):
    if already_mined(repo, "pull_requests"):
        print(f"  [skip] pull_requests already mined for {repo}")
        return

    print(f"\n[pull_requests] mining {repo} ...")
    records = []

    for pr in tqdm(
        paginate(f"/repos/{repo}/pulls", params={"state": "all", "sort": "created", "direction": "asc"}),
        desc="  fetching PRs"
    ):
        number = pr["number"]
        body = pr.get("body", "") or ""
        created_at = pr.get("created_at")
        merged_at = pr.get("merged_at")
        closed_at = pr.get("closed_at")

        # Issues this PR closes (Q49, Q52 ground truth)
        closes_issues = parse_closes(body)

        # Fetch reviews (Q5, Q47, Q50 ground truth)
        reviews = list(paginate(f"/repos/{repo}/pulls/{number}/reviews"))
        review_records = [
            {
                "reviewer": r["user"]["login"] if r.get("user") else None,
                "state": r["state"],          # APPROVED / CHANGES_REQUESTED / COMMENTED
                "submitted_at": r.get("submitted_at"),
                "body_length": len(r.get("body", "") or ""),
            }
            for r in reviews
        ]

        # Fetch review comments (inline code comments — good for Q48 rationale)
        review_comments = []
        for rc in paginate(f"/repos/{repo}/pulls/{number}/comments"):
            body_rc = rc.get("body", "") or ""
            if len(body_rc) < MIN_COMMENT_LENGTH:
                continue
            review_comments.append({
                "reviewer": rc["user"]["login"] if rc.get("user") else None,
                "path": rc.get("path"),
                "body": body_rc,
                "created_at": rc.get("created_at"),
            })

        # Requested reviewers at time of PR creation
        requested = [r["login"] for r in pr.get("requested_reviewers", [])]

        # Time metrics (Q50)
        hours_to_first_review = time_to_first_review(created_at, review_records)
        hours_open = None
        if created_at and closed_at:
            t0 = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
            hours_open = (t1 - t0).total_seconds() / 3600

        # Was it merged or closed without merge? (Q48 signal)
        outcome = "merged" if merged_at else ("closed" if closed_at else "open")

        # Did PR description contain a rationale? (Q48 proxy)
        has_rationale = len(body) >= MIN_COMMENT_LENGTH

        record = {
            "repo": repo,
            "number": number,
            "title": pr["title"],
            "body": body,
            "author": pr["user"]["login"] if pr.get("user") else None,
            "created_at": created_at,
            "merged_at": merged_at,
            "closed_at": closed_at,
            "outcome": outcome,
            "labels": [l["name"] for l in pr.get("labels", [])],
            "files_changed_count": pr.get("changed_files", 0),
            "additions": pr.get("additions", 0),
            "deletions": pr.get("deletions", 0),

            # Q49/Q52 ground truth: which issues does this PR fix
            "closes_issues": closes_issues,

            # Q5/Q47 ground truth: who reviewed
            "requested_reviewers": requested,
            "reviews": review_records,
            "unique_reviewers": list({r["reviewer"] for r in review_records if r["reviewer"]}),

            # Q50 ground truth: review latency
            "hours_to_first_review": hours_to_first_review,
            "hours_open": hours_open,

            # Q48 proxy: rationale quality signal
            "has_rationale": has_rationale,
            "review_comments": review_comments,
        }
        records.append(record)

    save_jsonl(repo, "pull_requests", records)
    print(f"  done — {len(records)} PRs mined")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=None)
    args = parser.parse_args()
    repos = [args.repo] if args.repo else REPOS
    for repo in repos:
        mine_pull_requests(repo)
