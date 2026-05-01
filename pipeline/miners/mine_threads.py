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


def format_issue_thread(issue):
    """Convert a mined issue record into a clean thread string."""
    lines = [
        f"ISSUE #{issue['number']}: {issue['title']}",
        f"Author: {issue.get('reporter', 'unknown')}",
        f"Date: {issue.get('created_at', '')}",
        f"Labels: {', '.join(issue.get('labels', []))}",
        f"State: {issue.get('state', '')}",
        "",
        issue.get("body", "")[:5000] or "[no body]",
        "",
        "--- COMMENTS ---",
    ]
    for c in (issue.get("comments") or [])[:20]:
        ts = c.get("created_at", "")
        author_line = f"@{c.get('author', '?')}"
        if ts:
            author_line += f" {ts}"
        lines.append(author_line + ":")
        lines.append((c.get("body") or "")[:5000])
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

        thread_text = format_issue_thread(issue)

        record = {
            "source": "issue",
            "repo": repo,
            "number": number,
            "title": issue["title"],
            "thread_text": thread_text,
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

            lines = [
                f"DISCUSSION #{number}: {d['title']}",
                f"Author: {d['author']['login']}",
                f"Date: {d.get('createdAt', '')}",
                "",
                (d.get("body") or ""),
                "",
                "--- COMMENTS ---",
            ]
            for c in d.get("comments", {}).get("nodes") or []:
                ts = c.get("createdAt", "")
                author_line = f"@{c['author']['login']}"
                if ts:
                    author_line += f" {ts}"
                lines.append(author_line + ":")
                lines.append((c.get("body") or ""))
                lines.append("---")

            if d.get("answer"):
                ts = d["answer"].get("createdAt", "")
                ans_line = f"[ACCEPTED ANSWER] @{d['answer']['author']['login']}"
                if ts:
                    ans_line += f" {ts}"
                lines.append(ans_line + ":")
                lines.append((d["answer"].get("body") or ""))

            record = {
                "source": "discussion",
                "repo": repo,
                "number": number,
                "title": d["title"],
                "thread_text": "\n".join(lines),
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
