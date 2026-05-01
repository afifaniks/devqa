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

import os
import re
import sys
import argparse
from datetime import datetime
from tqdm import tqdm

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.github_client import paginate_graphql
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


# Fetches PRs with reviews and inline review comments in one query.
# first: 20 PRs × (50 reviews + 20 threads × 5 comments) ≈ 3,020 nodes —
# within the 5,000-node GraphQL rate-limit budget.
_PRS_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(
      first: 20
      after: $cursor
      states: [OPEN, CLOSED, MERGED]
      orderBy: {field: CREATED_AT, direction: ASC}
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        body
        state
        createdAt
        mergedAt
        closedAt
        author { login }
        labels(first: 15) { nodes { name } }
        additions
        deletions
        changedFiles
        reviewRequests(first: 20) {
          nodes {
            requestedReviewer {
              ... on User { login }
              ... on Team { slug }
            }
          }
        }
        reviews(first: 50) {
          nodes {
            author { login }
            state
            submittedAt
            body
          }
        }
        reviewThreads(first: 20) {
          nodes {
            comments(first: 5) {
              nodes {
                author { login }
                path
                body
                createdAt
              }
            }
          }
        }
      }
    }
  }
}
"""


def mine_pull_requests(repo: str):
    if already_mined(repo, "pull_requests"):
        print(f"  [skip] pull_requests already mined for {repo}")
        return

    print(f"\n[pull_requests] mining {repo} ...")

    owner, name = repo.split("/")
    records = []

    for pr in tqdm(
        paginate_graphql(
            _PRS_QUERY,
            {"owner": owner, "name": name},
            lambda data: data["repository"]["pullRequests"],
        ),
        desc="  fetching PRs",
    ):
        number = pr["number"]
        body = pr.get("body", "") or ""
        created_at = pr.get("createdAt")
        merged_at = pr.get("mergedAt")
        closed_at = pr.get("closedAt")
        state = pr.get("state", "")  # OPEN / CLOSED / MERGED

        closes_issues = parse_closes(body)

        review_records = []
        for r in (pr.get("reviews") or {}).get("nodes", []):
            review_records.append(
                {
                    "reviewer": (r.get("author") or {}).get("login"),
                    "state": r.get("state"),
                    "submitted_at": r.get("submittedAt"),
                    "body_length": len(r.get("body", "") or ""),
                }
            )

        review_comments = []
        for thread in (pr.get("reviewThreads") or {}).get("nodes", []):
            for rc in (thread.get("comments") or {}).get("nodes", []):
                rc_body = rc.get("body", "") or ""
                if len(rc_body) < MIN_COMMENT_LENGTH:
                    continue
                review_comments.append(
                    {
                        "reviewer": (rc.get("author") or {}).get("login"),
                        "path": rc.get("path"),
                        "body": rc_body,
                        "created_at": rc.get("createdAt"),
                    }
                )

        requested = []
        for node in (pr.get("reviewRequests") or {}).get("nodes", []):
            reviewer = node.get("requestedReviewer") or {}
            login = reviewer.get("login") or reviewer.get("slug")
            if login:
                requested.append(login)

        hours_to_first_review = (
            time_to_first_review(created_at, review_records) if created_at else None
        )
        hours_open = None
        if created_at and closed_at:
            t0 = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
            hours_open = (t1 - t0).total_seconds() / 3600

        # GraphQL state is MERGED/CLOSED/OPEN; map to the outcome values used downstream
        if state == "MERGED":
            outcome = "merged"
        elif state == "CLOSED":
            outcome = "closed"
        else:
            outcome = "open"

        has_rationale = len(body) >= MIN_COMMENT_LENGTH

        record = {
            "repo": repo,
            "number": number,
            "title": pr["title"],
            "body": body,
            "author": (pr.get("author") or {}).get("login"),
            "created_at": created_at,
            "merged_at": merged_at,
            "closed_at": closed_at,
            "outcome": outcome,
            "labels": [
                node["name"] for node in (pr.get("labels") or {}).get("nodes", [])
            ],
            "files_changed_count": pr.get("changedFiles", 0),
            "additions": pr.get("additions", 0),
            "deletions": pr.get("deletions", 0),
            "closes_issues": closes_issues,
            "requested_reviewers": requested,
            "reviews": review_records,
            "unique_reviewers": list(
                {r["reviewer"] for r in review_records if r["reviewer"]}
            ),
            "hours_to_first_review": hours_to_first_review,
            "hours_open": hours_open,
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
