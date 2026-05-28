"""
Backfill `state` field into existing open_qa_pairs.jsonl records.

Looks up state from raw_threads.jsonl (keyed by repo + number).
Records with no matching thread get state="" and a warning.

Usage:
  python backfill_state.py                    # all repos with open_qa_pairs
  python backfill_state.py --repo psf/requests
"""

import sys
import os
import json
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.storage import load_jsonl, save_jsonl, repo_dir
from config import OUTPUT_DIR


def backfill(repo: str):
    threads = load_jsonl(repo, "raw_threads")
    if not threads:
        print(f"  [{repo}] no raw_threads.jsonl — skip")
        return

    state_map = {t["number"]: t.get("state", "") for t in threads}

    pairs = load_jsonl(repo, "open_qa_pairs")
    if not pairs:
        print(f"  [{repo}] no open_qa_pairs.jsonl — skip")
        return

    missing = 0
    already = 0
    updated = 0

    patched = []
    for rec in pairs:
        if "state" in rec and rec["state"]:
            already += 1
            patched.append(rec)
            continue

        num = rec.get("number")
        state = state_map.get(num, "")
        if not state:
            missing += 1
        else:
            updated += 1

        new_rec = {}
        for k, v in rec.items():
            new_rec[k] = v
            if k == "created_at":
                new_rec["state"] = state
        patched.append(new_rec)

    save_jsonl(repo, "open_qa_pairs", patched)
    print(f"  [{repo}] updated={updated}  already_had_state={already}  missing_thread={missing}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=None, help="Single repo (e.g. psf/requests); default: all")
    args = parser.parse_args()

    if args.repo:
        repos = [args.repo]
    else:
        repos = []
        for folder in os.listdir(OUTPUT_DIR):
            path = os.path.join(OUTPUT_DIR, folder, "open_qa_pairs.jsonl")
            if os.path.exists(path):
                repos.append(folder.replace("__", "/", 1))

    print(f"Backfilling state for {len(repos)} repo(s)...")
    for repo in sorted(repos):
        backfill(repo)
