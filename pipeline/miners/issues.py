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
from datetime import datetime
from tqdm import tqdm

sys.path.insert(0, "..")
from utils.github_client import paginate_graphql
from utils.storage import save_jsonl, already_mined
from config import REPOS, BUG_LABELS, MIN_COMMENT_LENGTH


DUPLICATE_PATTERNS = [
    re.compile(r"duplicate of #(\d+)", re.IGNORECASE),
    re.compile(r"dup of #(\d+)", re.IGNORECASE),
    re.compile(r"duplicates #(\d+)", re.IGNORECASE),
    re.compile(r"same as #(\d+)", re.IGNORECASE),
]

RELATED_PATTERNS = [
    re.compile(r"related to #(\d+)", re.IGNORECASE),
    re.compile(r"see also #(\d+)", re.IGNORECASE),
    re.compile(r"similar to #(\d+)", re.IGNORECASE),
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


# Fetches issues with labels, assignees, comments, and timeline items in one query.
# first: 20 issues × (50 comments + 50 timeline items) ≈ 2,020 nodes — within the
# 5,000-node GraphQL rate-limit budget.
_ISSUES_QUERY = """
query($owner: String!, $name: String!, $labels: [String!], $cursor: String) {
  repository(owner: $owner, name: $name) {
    issues(
      first: 20
      after: $cursor
      labels: $labels
      states: [OPEN, CLOSED]
      orderBy: {field: CREATED_AT, direction: ASC}
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        body
        state
        createdAt
        closedAt
        author { login }
        labels(first: 15) { nodes { name } }
        assignees(first: 10) { nodes { login } }
        comments(first: 50) {
          totalCount
          nodes {
            databaseId
            author { login }
            body
            createdAt
          }
        }
        timelineItems(
          first: 50
          itemTypes: [ASSIGNED_EVENT, LABELED_EVENT, CLOSED_EVENT, CROSS_REFERENCED_EVENT]
        ) {
          pageInfo { hasNextPage }
          nodes {
            __typename
            ... on AssignedEvent {
              createdAt
              assignee { ... on User { login } }
            }
            ... on LabeledEvent {
              createdAt
              label { name }
            }
            ... on ClosedEvent {
              createdAt
            }
            ... on CrossReferencedEvent {
              createdAt
              source {
                ... on Issue {
                  number
                  title
                  state
                }
              }
            }
          }
        }
      }
    }
  }
}
"""


def _parse_timeline(nodes: list) -> dict:
    assignments = []
    labels_applied = []
    first_bug_label_at = None
    first_assignee_after_bug = None
    closed_at = None
    cross_refs = []
    bug_label_seen = False
    bug_label_set = {l.lower() for l in BUG_LABELS}

    for node in nodes:
        typename = node.get("__typename")

        if typename == "AssignedEvent":
            assignee = (node.get("assignee") or {}).get("login")
            assigned_at = node.get("createdAt")
            if assignee:
                assignments.append({"assignee": assignee, "at": assigned_at})
                if bug_label_seen and first_assignee_after_bug is None:
                    first_assignee_after_bug = assignee

        elif typename == "LabeledEvent":
            label_name = (node.get("label") or {}).get("name", "")
            labels_applied.append({"label": label_name, "at": node.get("createdAt")})
            if label_name.lower() in bug_label_set and not bug_label_seen:
                first_bug_label_at = node.get("createdAt")
                bug_label_seen = True

        elif typename == "ClosedEvent":
            closed_at = node.get("createdAt")

        elif typename == "CrossReferencedEvent":
            source = node.get("source") or {}
            cross_refs.append({
                "ref_number": source.get("number"),
                "ref_title": source.get("title"),
                "ref_state": (source.get("state") or "").lower(),
                "at": node.get("createdAt"),
            })

    return {
        "assignments": assignments,
        "labels_applied": labels_applied,
        "first_bug_label_at": first_bug_label_at,
        "first_assignee_after_bug": first_assignee_after_bug,
        "closed_at": closed_at,
        "cross_refs": cross_refs,
    }


def mine_issues(repo: str):
    if already_mined(repo, "issues"):
        print(f"  [skip] issues already mined for {repo}")
        return

    print(f"\n[issues] mining {repo} ...")

    owner, name = repo.split("/")
    labels = BUG_LABELS if BUG_LABELS else None

    raw_issues = list(tqdm(
        paginate_graphql(
            _ISSUES_QUERY,
            {"owner": owner, "name": name, "labels": labels},
            lambda data: data["repository"]["issues"],
        ),
        desc="  fetching issues"
    ))

    records = []
    for issue in tqdm(raw_issues, desc="  processing issues"):
        number = issue["number"]
        body = issue.get("body", "") or ""
        labels_list = [l["name"] for l in (issue.get("labels") or {}).get("nodes", [])]

        dup_refs_body = parse_duplicate_refs(body)
        related_refs_body = parse_related_refs(body)

        is_duplicate = (
            "duplicate" in [l.lower() for l in labels_list]
            or len(dup_refs_body) > 0
        )

        created_at = issue.get("createdAt")
        closed_at_raw = issue.get("closedAt")
        time_to_close_hours = None
        if created_at and closed_at_raw:
            t0 = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(closed_at_raw.replace("Z", "+00:00"))
            time_to_close_hours = (t1 - t0).total_seconds() / 3600

        priority = None
        for label in labels_list:
            ll = label.lower()
            if any(p in ll for p in ["p0", "p1", "p2", "critical", "high", "medium", "low"]):
                priority = label
                break

        timeline_nodes = (issue.get("timelineItems") or {}).get("nodes", [])
        events = _parse_timeline(timeline_nodes)

        comment_data = issue.get("comments") or {}
        comment_count = comment_data.get("totalCount", 0)
        comments = []
        for c in comment_data.get("nodes", []):
            cbody = c.get("body", "") or ""
            if len(cbody) < MIN_COMMENT_LENGTH:
                continue
            comments.append({
                "id": c.get("databaseId"),
                "author": (c.get("author") or {}).get("login"),
                "body": cbody,
                "created_at": c.get("createdAt"),
                "duplicate_refs": parse_duplicate_refs(cbody),
                "related_refs": parse_related_refs(cbody),
            })

        all_dup_refs = dup_refs_body[:]
        all_related_refs = related_refs_body[:]
        for c in comments:
            all_dup_refs.extend(c["duplicate_refs"])
            all_related_refs.extend(c["related_refs"])

        record = {
            "repo": repo,
            "number": number,
            "title": issue["title"],
            "body": body,
            "state": issue["state"].lower(),
            "created_at": created_at,
            "closed_at": closed_at_raw,
            "reporter": (issue.get("author") or {}).get("login"),
            "labels": labels_list,
            "assignees": [n["login"] for n in (issue.get("assignees") or {}).get("nodes", [])],
            "first_assignee_after_bug_label": events["first_assignee_after_bug"],
            "first_bug_label_at": events["first_bug_label_at"],
            "is_duplicate": is_duplicate,
            "duplicate_of": all_dup_refs,
            "related_issues": all_related_refs,
            "cross_refs": events["cross_refs"],
            "priority_label": priority,
            "time_to_close_hours": time_to_close_hours,
            "assignment_history": events["assignments"],
            "label_history": events["labels_applied"],
            "comments": comments,
            "comment_count": comment_count,
        }
        records.append(record)

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
