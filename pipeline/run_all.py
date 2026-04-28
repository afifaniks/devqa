"""
Master pipeline script — runs all miners in order, then builds QA pairs.

Usage:
    python run_all.py                        # mine all configured repos
    python run_all.py --repo microsoft/vscode  # mine one repo only
    python run_all.py --skip-ci              # skip CI runs (slow)
    python run_all.py --only-qa             # only rebuild QA pairs (re-use existing data)
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from config import REPOS
from miners.issues import mine_issues
from miners.commits import mine_commits, run_szz
from miners.pull_requests import mine_pull_requests
from miners.ci_runs import mine_ci_runs
from miners.contributors import mine_contributors
from miners.qa_builder import build_all_pairs


def run_pipeline(repo: str, skip_ci: bool = False, only_qa: bool = False):
    print(f"\n{'='*60}")
    print(f"  PIPELINE: {repo}")
    print(f"{'='*60}")

    if not only_qa:
        # Step 1: Issues (most important — run first)
        mine_issues(repo)

        # Step 2: Commits + SZZ (slowest — fetches every commit)
        mine_commits(repo)
        run_szz(repo)

        # Step 3: Pull requests
        mine_pull_requests(repo)

        # Step 4: CI runs (optional — can be slow for large repos)
        if not skip_ci:
            mine_ci_runs(repo)

        # Step 5: Contributors (depends on commits + issues + PRs being done)
        mine_contributors(repo)

    # Step 6: Build QA pairs from all mined data
    build_all_pairs(repo)

    print(f"\n[done] {repo} pipeline complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GitHub mining pipeline")
    parser.add_argument("--repo", default=None, help="Mine a single repo (e.g. microsoft/vscode)")
    parser.add_argument("--skip-ci", action="store_true", help="Skip CI run mining")
    parser.add_argument("--only-qa", action="store_true", help="Skip mining, only rebuild QA pairs")
    args = parser.parse_args()

    repos = [args.repo] if args.repo else REPOS
    for repo in repos:
        run_pipeline(repo, skip_ci=args.skip_ci, only_qa=args.only_qa)

    print(f"\nAll done. QA pairs are in output/<repo>/qa_pairs.jsonl")
