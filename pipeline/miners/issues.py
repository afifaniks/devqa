"""
Issues miner — covers questions:
  Q1-6   (who is working on what)
  Q28-31 (work item progress)
  Q43-44 (who changed/commented on a defect)
  Q46    (which conversations mention me)
  Q53    (duplicate detection — ground truth)
  Q54    (bug assignment / triage)
  Q57    (severity/priority)
  Q58    (related bugs)
  Q59    (time-to-fix)
  Q60    (full bug lifecycle)
"""

import re
import sys
import argparse
from datetime import datetime, timezone
from tqdm import tqdm

sys.path.insert(0, "..")
from utils.github_client import paginate, get
from utils.storage import save_jsonl, already_mined
from config import REPOS, BUG_LABELS, MIN_COMMENT_LENGTH


# Patterns that indicate a duplicate reference
DUPLICATE_PATTERNS = [
    re.compile(r"duplicate of #(\d+)", re.IGNORECASE),
    re.compile(r"dup of #(\d+)", re.IGNORECASE),
    re.compile(r"duplicates #(\d+)", re.IGNORECASE),
    re.compile(r"same as #(\d+)", re.IGNORECASE),
]

# Patterns that indicate a related issue reference
RELATED_PATTERNS = [
    re.compile(r"related to #(\d+)", re.IGNORECASE),
    re.compile(r"see also #(\d+)", re.IGNORECASE),
    re.compile(r"similar to #(\d+)", re.IGNORECASE),
]

# Closing keywords that link an issue to a PR/commit
CLOSING_PATTERNS = [
    re.compile(r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?) #(\d+)", re.IGNORECASE),
]


def parse_duplicate_refs(text: str) -> list:
    refs = []
    for pattern in DUPLICATE_PATTERNS:
        refs.extend(pattern.findall(text or ""))
    return [int(r) for r in refs]


def parse_related_refs(text: str) -> list:
    refs = []
    for pattern in RELATED_PATTERNS:
        refs.extend(pattern.findall(text or ""))
    return [int(r) for r in refs]


def mine_issue_events(repo: str, issue_number: int) -> dict:
    """
    Fetch the full timeline for one issue.
    Returns structured data: assignments, labels, cross-references, close event.
    """
    events = list(paginate(
        f"/repos/{repo}/issues/{issue_number}/timeline",
        params={"per_page": 100}
    ))

    assignments = []
    labels_applied = []
    first_bug_label_at = None
    first_assignee_after_bug = None
    closed_at = None
    cross_refs = []

    bug_label_seen = False

    for event in events:
        etype = event.get("event")

        if etype == "assigned":
            assignee = event.get("assignee", {}).get("login")
            assigned_at = event.get("created_at")
            assignments.append({"assignee": assignee, "at": assigned_at})
            # Ground truth for Q54: first assignee after bug label
            if bug_label_seen and first_assignee_after_bug is None:
                first_assignee_after_bug = assignee

        elif etype == "labeled":
            label_name = event.get("label", {}).get("name", "")
            labels_applied.append({"label": label_name, "at": event.get("created_at")})
            if label_name.lower() in [l.lower() for l in BUG_LABELS]:
                if not bug_label_seen:
                    first_bug_label_at = event.get("created_at")
                    bug_label_seen = True

        elif etype == "closed":
            closed_at = event.get("created_at")

        elif etype == "cross-referenced":
            source = event.get("source", {})
            ref_issue = source.get("issue", {})
            cross_refs.append({
                "ref_number": ref_issue.get("number"),
                "ref_title": ref_issue.get("title"),
                "ref_state": ref_issue.get("state"),
                "at": event.get("created_at"),
            })

    return {
        "assignments": assignments,
        "labels_applied": labels_applied,
        "first_bug_label_at": first_bug_label_at,
        "first_assignee_after_bug": first_assignee_after_bug,
        "closed_at": closed_at,
        "cross_refs": cross_refs,
    }


def mine_issue_comments(repo: str, issue_number: int) -> list:
    """Fetch all comments on an issue, keeping only substantive ones."""
    comments = []
    for c in paginate(f"/repos/{repo}/issues/{issue_number}/comments"):
        body = c.get("body", "") or ""
        if len(body) < MIN_COMMENT_LENGTH:
            continue
        comments.append({
            "id": c["id"],
            "author": c["user"]["login"],
            "body": body,
            "created_at": c["created_at"],
            "duplicate_refs": parse_duplicate_refs(body),
            "related_refs": parse_related_refs(body),
        })
    return comments


def mine_issues(repo: str):
    if already_mined(repo, "issues"):
        print(f"  [skip] issues already mined for {repo}")
        return

    print(f"\n[issues] mining {repo} ...")

    # Fetch all issues labelled as bugs
    label_filter = ",".join(BUG_LABELS) if BUG_LABELS else None
    params = {"state": "all", "sort": "created", "direction": "asc"}
    if label_filter:
        params["labels"] = label_filter

    raw_issues = list(tqdm(
        paginate(f"/repos/{repo}/issues", params=params),
        desc="  fetching issues"
    ))

    # Filter out pull requests (GitHub returns PRs in /issues endpoint)
    raw_issues = [i for i in raw_issues if "pull_request" not in i]

    records = []
    for issue in tqdm(raw_issues, desc="  enriching issues"):
        number = issue["number"]
        body = issue.get("body", "") or ""
        labels = [l["name"] for l in issue.get("labels", [])]

        # Parse duplicate/related references from the issue body
        dup_refs_body = parse_duplicate_refs(body)
        related_refs_body = parse_related_refs(body)

        # Determine if this issue was closed as a duplicate
        is_duplicate = (
            "duplicate" in [l.lower() for l in labels]
            or len(dup_refs_body) > 0
        )

        # Time to fix (in hours) — only meaningful if issue is closed
        created_at = issue.get("created_at")
        closed_at_raw = issue.get("closed_at")
        time_to_close_hours = None
        if created_at and closed_at_raw:
            t0 = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(closed_at_raw.replace("Z", "+00:00"))
            time_to_close_hours = (t1 - t0).total_seconds() / 3600

        # Priority/severity from labels
        priority = None
        for label in labels:
            ll = label.lower()
            if any(p in ll for p in ["p0", "p1", "p2", "critical", "high", "medium", "low"]):
                priority = label
                break

        # Get full timeline (assignments, labels, cross-refs)
        events = mine_issue_events(repo, number)

        # Get comments
        comments = mine_issue_comments(repo, number)

        # Collect all duplicate refs from body + comments
        all_dup_refs = dup_refs_body[:]
        all_related_refs = related_refs_body[:]
        for c in comments:
            all_dup_refs.extend(c["duplicate_refs"])
            all_related_refs.extend(c["related_refs"])

        record = {
            # Identity
            "repo": repo,
            "number": number,
            "title": issue["title"],
            "body": body,
            "state": issue["state"],
            "created_at": created_at,
            "closed_at": closed_at_raw,
            "reporter": issue["user"]["login"],
            "labels": labels,

            # Q54 ground truth: who was assigned after bug label applied
            "assignees": [a["login"] for a in issue.get("assignees", [])],
            "first_assignee_after_bug_label": events["first_assignee_after_bug"],
            "first_bug_label_at": events["first_bug_label_at"],

            # Q53 ground truth: duplicate detection
            "is_duplicate": is_duplicate,
            "duplicate_of": all_dup_refs,

            # Q58: related issues
            "related_issues": all_related_refs,
            "cross_refs": events["cross_refs"],

            # Q57: severity
            "priority_label": priority,

            # Q59: time to fix
            "time_to_close_hours": time_to_close_hours,

            # Q60: full lifecycle
            "assignment_history": events["assignments"],
            "label_history": events["labels_applied"],

            # Comments (ground truth for interpretive questions)
            "comments": comments,
            "comment_count": len(comments),
        }
        records.append(record)

        # Save incrementally every 10 issues in case of interruption
        if len(records) % 10 == 0:
            print(f"  saving {len(records)} issues so far...")
            save_jsonl(repo, "issues", records)

    save_jsonl(repo, "issues", records)
    print(f"  done — {len(records)} bug issues mined")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=None)
    args = parser.parse_args()
    repos = [args.repo] if args.repo else REPOS
    for repo in repos:
        mine_issues(repo)
