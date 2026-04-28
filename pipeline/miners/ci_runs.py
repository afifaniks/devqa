"""
CI runs miner — covers questions:
  Q32-35 (what caused the build to break, who caused it)
  Q61    (flaky vs genuinely failing test)
  Q62    (which CI stage is the bottleneck)
  Q63    (how often does this component break the build)
  Q64    (which contributor's changes most frequently break CI)
"""

import sys
import argparse
from collections import defaultdict
from tqdm import tqdm

sys.path.insert(0, "..")
from utils.github_client import paginate, get
from utils.storage import save_jsonl, already_mined
from config import REPOS


def mine_ci_runs(repo: str):
    if already_mined(repo, "ci_runs"):
        print(f"  [skip] ci_runs already mined for {repo}")
        return

    print(f"\n[ci_runs] mining {repo} ...")

    runs = []
    failure_counts_by_actor = defaultdict(int)
    failure_counts_by_workflow = defaultdict(int)
    run_counts_by_actor = defaultdict(int)

    for run in tqdm(
        paginate(f"/repos/{repo}/actions/runs", params={"per_page": 100}),
        desc="  fetching runs"
    ):
        run_id = run["id"]
        conclusion = run.get("conclusion")          # success / failure / cancelled / skipped
        status = run.get("status")                  # completed / in_progress / queued
        actor = run.get("triggering_actor", {}) or {}
        actor_login = actor.get("login")
        workflow_name = run.get("name")
        head_sha = run.get("head_sha")
        head_branch = run.get("head_branch")
        pr_numbers = [pr["number"] for pr in run.get("pull_requests", [])]

        run_counts_by_actor[actor_login] += 1
        if conclusion == "failure":
            failure_counts_by_actor[actor_login] += 1
            failure_counts_by_workflow[workflow_name] += 1

        # Fetch failed jobs for this run (Q32-35: which step broke)
        failed_jobs = []
        if conclusion == "failure":
            try:
                jobs_data = get(f"/repos/{repo}/actions/runs/{run_id}/jobs")
                for job in jobs_data.get("jobs", []):
                    if job.get("conclusion") == "failure":
                        failed_steps = [
                            s["name"] for s in job.get("steps", [])
                            if s.get("conclusion") == "failure"
                        ]
                        failed_jobs.append({
                            "job_name": job["name"],
                            "failed_steps": failed_steps,
                            "started_at": job.get("started_at"),
                            "completed_at": job.get("completed_at"),
                        })
            except Exception:
                pass

        record = {
            "repo": repo,
            "run_id": run_id,
            "workflow_name": workflow_name,
            "head_sha": head_sha,
            "head_branch": head_branch,
            "actor": actor_login,
            "status": status,
            "conclusion": conclusion,
            "created_at": run.get("created_at"),
            "updated_at": run.get("updated_at"),
            "pr_numbers": pr_numbers,

            # Q32-35 ground truth: what failed
            "failed_jobs": failed_jobs,

            # Used to compute Q63/Q64 aggregates
            "is_failure": conclusion == "failure",
        }
        runs.append(record)

    # Q64 ground truth: who breaks CI most
    failure_rates = {
        actor: {
            "failures": failure_counts_by_actor[actor],
            "total_runs": run_counts_by_actor[actor],
            "failure_rate": failure_counts_by_actor[actor] / max(run_counts_by_actor[actor], 1),
        }
        for actor in run_counts_by_actor
    }

    # Q62 ground truth: which workflow (stage) fails most
    workflow_failure_summary = [
        {"workflow": wf, "failure_count": count}
        for wf, count in sorted(failure_counts_by_workflow.items(), key=lambda x: -x[1])
    ]

    save_jsonl(repo, "ci_runs", runs)
    save_jsonl(repo, "ci_actor_failure_rates", [
        {"repo": repo, "actor": k, **v} for k, v in failure_rates.items()
    ])
    save_jsonl(repo, "ci_workflow_failures", [
        {"repo": repo, **w} for w in workflow_failure_summary
    ])

    print(f"  done — {len(runs)} CI runs mined")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=None)
    args = parser.parse_args()
    repos = [args.repo] if args.repo else REPOS
    for repo in repos:
        mine_ci_runs(repo)
