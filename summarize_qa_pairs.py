#!/usr/bin/env python3
"""Combine all natural_qa_pairs.jsonl files from output/ and summarize question instances."""

import json
from collections import defaultdict
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"


def load_all_pairs(output_dir: Path) -> list[dict]:
    records = []
    for jsonl_file in sorted(output_dir.glob("*/natural_qa_pairs.jsonl")):
        with jsonl_file.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def summarize(records: list[dict]) -> None:
    # Count instances per question_id, track question text and repos
    question_texts: dict[str, str] = {}
    question_counts: dict[str, int] = defaultdict(int)
    question_repos: dict[str, set[str]] = defaultdict(set)

    for r in records:
        qid = r["question_id"]
        question_counts[qid] += 1
        question_repos[qid].add(r["repo"])
        if qid not in question_texts:
            question_texts[qid] = r["question_text"]

    total_records = len(records)
    unique_questions = len(question_counts)
    repos = sorted({r["repo"] for r in records})

    print(f"=== QA Pairs Summary ===")
    print(f"Repos processed   : {len(repos)}")
    for repo in repos:
        count = sum(1 for r in records if r["repo"] == repo)
        print(f"  {repo}: {count} pairs")
    print(f"Total pairs       : {total_records}")
    print(f"Unique question IDs: {unique_questions}")
    print()

    # Sort by question_id numerically where possible
    def sort_key(qid: str) -> tuple:
        prefix = "".join(c for c in qid if not c.isdigit())
        num = "".join(c for c in qid if c.isdigit())
        return (prefix, int(num) if num else 0)

    print(f"{'Question ID':<12} {'Count':>5}  {'Repos':>6}  Question Text")
    print("-" * 100)
    for qid in sorted(question_counts, key=sort_key):
        count = question_counts[qid]
        repo_count = len(question_repos[qid])
        text = question_texts[qid]
        truncated = text[:70] + "..." if len(text) > 70 else text
        print(f"{qid:<12} {count:>5}  {repo_count:>6}  {truncated}")

    print()
    print(f"Questions with multiple instances (count > 1):")
    multi = [
        (qid, question_counts[qid])
        for qid in question_counts
        if question_counts[qid] > 1
    ]
    if multi:
        for qid, count in sorted(multi, key=lambda x: -x[1]):
            print(f"  {qid}: {count} instances — {question_texts[qid][:80]}")
    else:
        print("  None")


if __name__ == "__main__":
    records = load_all_pairs(OUTPUT_DIR)
    if not records:
        print("No natural_qa_pairs.jsonl files found under output/")
    else:
        summarize(records)
