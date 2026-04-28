"""
QA Pair Builder — assembles (question, ground_truth_answer, required_artifacts)
triples from all mined data.

Run this AFTER all miners have completed.
Output: qa_pairs.jsonl — one record per question instance, ready for LLM evaluation.
"""

import sys
import argparse
import random
from tqdm import tqdm

sys.path.insert(0, "..")
from utils.storage import load_jsonl, save_jsonl
from config import REPOS


def build_duplicate_pairs(repo: str) -> list:
    """
    Q53: Has this bug/crash been reported before?
    Ground truth: issues with 'duplicate_of' populated.
    Produces positive (duplicate) and negative (non-duplicate) pairs.
    """
    issues = load_jsonl(repo, "issues")
    by_number = {i["number"]: i for i in issues}

    pairs = []
    positives = [i for i in issues if i.get("duplicate_of")]

    for issue in positives:
        for original_num in issue["duplicate_of"]:
            original = by_number.get(original_num)
            if not original:
                continue
            pairs.append({
                "question_id": "Q53",
                "question": f"Has this bug been reported before?\n\nTitle: {issue['title']}\nBody: {issue['body'][:500]}",
                "ground_truth": {
                    "is_duplicate": True,
                    "duplicate_of_issue": original_num,
                    "original_title": original["title"],
                },
                "artifacts_needed": {
                    "issue_body": issue["body"],
                    "issue_title": issue["title"],
                    "candidate_issues": [
                        {"number": original_num, "title": original["title"], "body": original.get("body", "")[:300]}
                    ],
                },
                "tier": 1,
                "repo": repo,
                "issue_number": issue["number"],
            })

    # Add negatives (non-duplicates sampled randomly)
    non_dupes = [i for i in issues if not i.get("duplicate_of") and not i.get("is_duplicate")]
    for i in range(min(len(positives), len(non_dupes))):
        a, b = non_dupes[i], random.choice(non_dupes)
        if a["number"] == b["number"]:
            continue
        pairs.append({
            "question_id": "Q53",
            "question": f"Has this bug been reported before?\n\nTitle: {a['title']}\nBody: {a['body'][:500]}",
            "ground_truth": {"is_duplicate": False, "duplicate_of_issue": None},
            "artifacts_needed": {
                "issue_body": a["body"],
                "issue_title": a["title"],
                "candidate_issues": [{"number": b["number"], "title": b["title"], "body": b.get("body", "")[:300]}],
            },
            "tier": 1,
            "repo": repo,
            "issue_number": a["number"],
        })

    return pairs


def build_assignment_pairs(repo: str) -> list:
    """
    Q54: Who should be assigned this bug?
    Ground truth: first assignee after the bug label was applied.
    """
    issues = load_jsonl(repo, "issues")
    contributors = {c["login"]: c for c in load_jsonl(repo, "contributors")}

    pairs = []
    for issue in issues:
        gt_assignee = issue.get("first_assignee_after_bug_label")
        if not gt_assignee:
            continue

        # Build context: top contributors for the files this bug might touch
        # (we don't have file-bug mapping yet, so use general contributor list)
        top_contributors = sorted(
            contributors.values(),
            key=lambda c: -c.get("activity_score", 0)
        )[:10]

        pairs.append({
            "question_id": "Q54",
            "question": f"Who should be assigned this bug?\n\nTitle: {issue['title']}\nBody: {issue['body'][:500]}\nLabels: {', '.join(issue['labels'])}",
            "ground_truth": {
                "assignee": gt_assignee,
            },
            "artifacts_needed": {
                "issue": {"title": issue["title"], "body": issue["body"][:500], "labels": issue["labels"]},
                "contributor_profiles": [
                    {"login": c["login"], "top_files": c["top_files"][:5], "total_commits": c["total_commits"]}
                    for c in top_contributors
                ],
            },
            "tier": 2,
            "repo": repo,
            "issue_number": issue["number"],
        })

    return pairs


def build_regression_pairs(repo: str) -> list:
    """
    Q56: Which commit introduced this regression?
    Ground truth: SZZ inducing commit.
    """
    szz_pairs = load_jsonl(repo, "szz_pairs")
    pairs = []

    for pair in szz_pairs:
        gt = pair.get("ground_truth_q56", {})
        if not gt:
            continue
        pairs.append({
            "question_id": "Q56",
            "question": gt["question"],
            "ground_truth": {
                "inducing_sha": pair["inducing_sha"],
                "inducing_author": pair["inducing_author"],
                "file": pair["file"],
            },
            "artifacts_needed": {
                "fix_commit_sha": pair["fix_sha"],
                "file": pair["file"],
                "recent_commits_on_file": [],  # populated from commits.jsonl if needed
            },
            "tier": 1,
            "repo": repo,
            "issue_number": pair["issue_number"],
        })

    return pairs


def build_build_breakage_pairs(repo: str) -> list:
    """
    Q32-35: What/who caused this build to break?
    Ground truth: CI run failure linked to a commit/PR.
    """
    ci_runs = load_jsonl(repo, "ci_runs")
    pairs = []

    for run in ci_runs:
        if not run.get("is_failure") or not run.get("failed_jobs"):
            continue

        failed_steps = []
        for job in run["failed_jobs"]:
            failed_steps.extend(job.get("failed_steps", []))

        # Q32
        pairs.append({
            "question_id": "Q32",
            "question": f"What caused this build to break? (Run ID: {run['run_id']}, Workflow: {run['workflow_name']})",
            "ground_truth": {
                "failed_jobs": run["failed_jobs"],
                "failed_steps": failed_steps,
                "triggering_sha": run["head_sha"],
            },
            "artifacts_needed": {
                "ci_run": {k: run[k] for k in ["run_id", "workflow_name", "head_sha", "head_branch", "created_at"]},
                "failed_jobs": run["failed_jobs"],
            },
            "tier": 1,
            "repo": repo,
        })

        # Q33
        if run.get("actor"):
            pairs.append({
                "question_id": "Q33",
                "question": f"Who caused this build to break? (Run ID: {run['run_id']})",
                "ground_truth": {"actor": run["actor"]},
                "artifacts_needed": {
                    "ci_run": {k: run[k] for k in ["run_id", "workflow_name", "head_sha", "actor"]},
                },
                "tier": 1,
                "repo": repo,
            })

    return pairs


def build_ownership_pairs(repo: str) -> list:
    """
    Q18/Q19: Who owns this piece of code?
    Ground truth: most recent / most frequent modifier from file_experts.jsonl
    """
    file_experts = load_jsonl(repo, "file_experts")
    commits = load_jsonl(repo, "commits")

    # Build most recent modifier index
    most_recent = {}
    for commit in sorted(commits, key=lambda c: c.get("committed_at", "")):
        for fp in commit.get("files_changed", []):
            most_recent[fp] = commit.get("author_login")

    pairs = []
    for entry in file_experts:
        fp = entry["file"]
        experts = entry.get("experts", [])
        if not experts:
            continue

        # Q18: most recent modifier
        recent_modifier = most_recent.get(fp)
        if recent_modifier:
            pairs.append({
                "question_id": "Q18",
                "question": f"Who most recently modified this file?\n\nFile: {fp}",
                "ground_truth": {"login": recent_modifier},
                "artifacts_needed": {"file_path": fp, "recent_commits": []},
                "tier": 1,
                "repo": repo,
            })

        # Q19: most frequent modifier
        pairs.append({
            "question_id": "Q19",
            "question": f"Who has modified this file most frequently?\n\nFile: {fp}",
            "ground_truth": {"login": experts[0]["login"], "commit_count": experts[0]["commits"]},
            "artifacts_needed": {"file_path": fp, "contributor_profiles": experts[:5]},
            "tier": 1,
            "repo": repo,
        })

    return pairs


def build_pr_review_time_pairs(repo: str) -> list:
    """
    Q50: How long does PR review typically take for this component?
    Ground truth: median hours_to_first_review for PRs touching the same directory.
    """
    import statistics
    prs = load_jsonl(repo, "pull_requests")

    # Group PRs by top-level directory of changed files
    # (we don't have file lists per PR directly, but we can use labels as proxy)
    review_times = [
        pr["hours_to_first_review"]
        for pr in prs
        if pr.get("hours_to_first_review") is not None
    ]
    if len(review_times) < 5:
        return []

    median_hours = statistics.median(review_times)
    return [{
        "question_id": "Q50",
        "question": f"How long does PR review typically take in {repo}?",
        "ground_truth": {
            "median_hours_to_first_review": round(median_hours, 1),
            "sample_size": len(review_times),
        },
        "artifacts_needed": {"pr_review_history": review_times[:50]},
        "tier": 1,
        "repo": repo,
    }]


def build_all_pairs(repo: str):
    print(f"\n[qa_builder] building QA pairs for {repo} ...")
    all_pairs = []

    builders = [
        ("Q53 duplicates",   build_duplicate_pairs),
        ("Q54 assignment",   build_assignment_pairs),
        ("Q56 regression",   build_regression_pairs),
        ("Q32-35 breakage",  build_build_breakage_pairs),
        ("Q18-19 ownership", build_ownership_pairs),
        ("Q50 review time",  build_pr_review_time_pairs),
    ]

    for label, fn in builders:
        try:
            pairs = fn(repo)
            print(f"  {label}: {len(pairs)} pairs")
            all_pairs.extend(pairs)
        except Exception as e:
            print(f"  [warn] {label} failed: {e}")

    save_jsonl(repo, "qa_pairs", all_pairs)
    print(f"  total: {len(all_pairs)} QA pairs saved")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=None)
    args = parser.parse_args()
    repos = [args.repo] if args.repo else REPOS
    for repo in repos:
        build_all_pairs(repo)
