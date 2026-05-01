"""
Mines raw GitHub threads — issue comment threads and Discussions —
and saves them as-is without any classification.

Run once per repo. Output: raw_threads.jsonl
Each record is a self-contained thread with all the text needed
for classification, plus metadata for traceability.
"""

import sys
import argparse
import os
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.github_client import paginate, paginate_graphql
from utils.storage import append_record, load_checkpoint, save_checkpoint, already_mined
from config import REPOS


def build_issue_comments(issue):
    """Build a structured comment list from a mined issue record.

    Index 0 is always the issue body (role='body'); subsequent entries are comments.
    Each entry has a short ID (c0, c1, …) for use in thread_text and the UI.
    """
    comments = [
        {
            "id": "c0",
            "author": issue.get("reporter", "unknown"),
            "timestamp": issue.get("created_at", ""),
            "body": (issue.get("body", "") or "")[:5000],
            "is_accepted": False,
            "role": "body",
        }
    ]
    for i, c in enumerate((issue.get("comments") or [])[:20], start=1):
        comments.append(
            {
                "id": f"c{i}",
                "author": c.get("author", "?"),
                "timestamp": c.get("created_at", ""),
                "body": (c.get("body") or "")[:5000],
                "is_accepted": False,
                "role": "comment",
            }
        )
    return comments


def format_issue_thread(issue, comments):
    """Convert a mined issue + structured comments into a thread string.

    Each comment block is prefixed with its ID (e.g. [c1]) so the LLM can
    reference specific comments when returning question_comment_id/answer_comment_id.
    """
    c0 = comments[0]
    lines = [
        f"ISSUE #{issue['number']}: {issue['title']}",
        f"Author: {c0['author']}",
        f"Date: {c0['timestamp']}",
        f"Labels: {', '.join(issue.get('labels', []))}",
        f"State: {issue.get('state', '')}",
        "",
        "[c0]",
        c0["body"] or "[no body]",
        "",
        "--- COMMENTS ---",
    ]
    for c in comments[1:]:
        author_line = f"[{c['id']}] @{c['author']}"
        if c["timestamp"]:
            author_line += f" {c['timestamp']}"
        lines.append(author_line + ":")
        lines.append(c["body"])
        lines.append("---")
    return "\n".join(lines)


def mine_issue_threads(repo):
    """
    Mine issue threads from already-mined issues.jsonl.
    Requires issues.py to have run first.
    """
    from utils.storage import load_jsonl

    issues = load_jsonl(repo, "issues")

    if not issues:
        print("  [warn] no issues found — run miners/issues.py first")
        return 0

    done = load_checkpoint(repo, "raw_threads_issues")
    count = 0

    for issue in tqdm(issues, desc="  formatting issue threads"):
        number = issue["number"]
        if number in done:
            continue

        # Skip issues with no comments — no chance of a Q&A exchange
        if issue.get("comment_count", 0) < 1:
            done.add(number)
            continue

        comments = build_issue_comments(issue)
        thread_text = format_issue_thread(issue, comments)

        record = {
            "source": "issue",
            "repo": repo,
            "number": number,
            "title": issue["title"],
            "thread_text": thread_text,
            "comments": comments,
            "comment_count": issue.get("comment_count", 0),
            "labels": issue.get("labels", []),
            "state": issue.get("state", ""),
            "created_at": issue.get("created_at", ""),
            "closed_at": issue.get("closed_at", ""),
            "reporter": issue.get("reporter", ""),
            "url": f"https://github.com/{repo}/issues/{number}",
        }

        append_record(repo, "raw_threads", record)
        done.add(number)
        count += 1

        if count % 100 == 0:
            save_checkpoint(repo, "raw_threads_issues", done)

    save_checkpoint(repo, "raw_threads_issues", done)
    print(f"  mined {count} issue threads")
    return count


_DISCUSSIONS_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    discussions(first: 50, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        body
        createdAt
        author { login }
        answer {
          body
          createdAt
          author { login }
        }
        comments(first: 15) {
          totalCount
          nodes {
            body
            createdAt
            author { login }
          }
        }
      }
    }
  }
}
"""


def build_discussion_comments(d):
    """Build a structured comment list from a discussion GraphQL node.

    Index 0 is the discussion body. Subsequent entries are comments.
    The accepted answer is marked is_accepted=True; if it wasn't already in
    the comments list (e.g. it was a nested reply) it is appended at the end.
    """
    comments = [
        {
            "id": "c0",
            "author": d["author"]["login"],
            "timestamp": d.get("createdAt", ""),
            "body": (d.get("body") or ""),
            "is_accepted": False,
            "role": "body",
        }
    ]

    ans_body = d["answer"]["body"] if d.get("answer") else None
    ans_author = d["answer"]["author"]["login"] if d.get("answer") else None
    accepted_matched = False

    for i, c in enumerate((d.get("comments", {}).get("nodes") or []), start=1):
        body = c.get("body") or ""
        author = c["author"]["login"]
        is_accepted = bool(ans_body is not None and body == ans_body and author == ans_author)
        if is_accepted:
            accepted_matched = True
        comments.append(
            {
                "id": f"c{i}",
                "author": author,
                "timestamp": c.get("createdAt", ""),
                "body": body,
                "is_accepted": is_accepted,
                "role": "comment",
            }
        )

    if d.get("answer") and not accepted_matched:
        comments.append(
            {
                "id": f"c{len(comments)}",
                "author": ans_author,
                "timestamp": d["answer"].get("createdAt", ""),
                "body": ans_body,
                "is_accepted": True,
                "role": "comment",
            }
        )

    return comments


def format_discussion_thread(d, comments):
    """Convert a discussion + structured comments into a thread string with IDs."""
    c0 = comments[0]
    lines = [
        f"DISCUSSION #{d['number']}: {d['title']}",
        f"Author: {c0['author']}",
        f"Date: {c0['timestamp']}",
        "",
        "[c0]",
        c0["body"] or "[no body]",
        "",
        "--- COMMENTS ---",
    ]
    for c in comments[1:]:
        prefix = f"[{c['id']}]"
        if c["is_accepted"]:
            prefix += " [ACCEPTED ANSWER]"
        author_line = f"{prefix} @{c['author']}"
        if c["timestamp"]:
            author_line += f" {c['timestamp']}"
        lines.append(author_line + ":")
        lines.append(c["body"])
        lines.append("---")
    return "\n".join(lines)


def mine_discussion_threads(repo):
    """
    Mine GitHub Discussions via GraphQL API.
    Fetches all discussions, not just answered ones,
    so you can inspect and filter during classification.
    """
    owner, name = repo.split("/")
    done = load_checkpoint(repo, "raw_threads_discussions")
    count = 0

    print("  fetching GitHub Discussions ...")
    try:
        nodes = paginate_graphql(
            _DISCUSSIONS_QUERY,
            {"owner": owner, "name": name},
            lambda data: data["repository"]["discussions"],
        )
        for d in nodes:
            number = d["number"]
            if number in done:
                continue

            comments = build_discussion_comments(d)
            thread_text = format_discussion_thread(d, comments)

            record = {
                "source": "discussion",
                "repo": repo,
                "number": number,
                "title": d["title"],
                "thread_text": thread_text,
                "comments": comments,
                "comment_count": d["comments"]["totalCount"],
                "has_accepted_answer": d.get("answer") is not None,
                "created_at": d.get("createdAt", ""),
                "author": d["author"]["login"],
                "url": f"https://github.com/{repo}/discussions/{number}",
            }

            append_record(repo, "raw_threads", record)
            done.add(number)
            count += 1

    except Exception as e:
        print(f"  [warn] GraphQL request failed: {e}")

    save_checkpoint(repo, "raw_threads_discussions", done)
    print(f"  mined {count} discussion threads")
    return count


def mine_threads(repo):
    print(f"\n[mine_threads] {repo}")

    issue_count = mine_issue_threads(repo)
    discussion_count = mine_discussion_threads(repo)

    total = issue_count + discussion_count
    print(
        f"\n  total threads saved: {total} → output/{repo.replace('/','__')}/raw_threads.jsonl"
    )
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=None)
    args = parser.parse_args()
    repos = [args.repo] if args.repo else REPOS
    for repo in repos:
        mine_threads(repo)
