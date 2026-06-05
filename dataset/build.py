"""
Build security benchmark dataset from human-verified security QA pairs.

Joins:
  security_verified_state.json  →  filter accepted
  output/<repo>/security_qa_pairs.jsonl  →  Q&A, hard_facts, comments
  output/<repo>/raw_threads.jsonl  →  labels, closed_at, reporter

Output: one JSONL record per accepted pair.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def repo_to_folder(repo: str) -> str:
    return repo.replace("/", "__")


def load_jsonl_index(path: Path, key: str) -> dict:
    if not path.exists():
        return {}
    index = {}
    with open(path) as f:
        for line in f:
            record = json.loads(line)
            index[record[key]] = record
    return index


def clean_comments(comments: list) -> list:
    keep = {"id", "author", "timestamp", "body", "role"}
    return [{k: v for k, v in c.items() if k in keep} for c in comments]


def build_record(
    entry_key: str,
    verified_entry: dict,
    qa_pair: dict,
    raw_thread: dict | None,
) -> dict:
    hard_facts = qa_pair.get("hard_facts", {})

    record = {
        "id": entry_key,
        "repo": qa_pair["repo"],
        "number": qa_pair["number"],
        "title": qa_pair["title"],
        "url": qa_pair["url"],
        "state": qa_pair.get("state"),
        "created_at": qa_pair.get("created_at"),
        "closed_at": raw_thread.get("closed_at") if raw_thread else None,
        "labels": raw_thread.get("labels", []) if raw_thread else [],
        "reporter": raw_thread.get("reporter") if raw_thread else None,
        "security_topic": qa_pair.get("security_topic"),
        "qa_summary": qa_pair.get("need_summary"),
        "question_comment_id": qa_pair.get("question_comment_id"),
        "answer_comment_id": qa_pair.get("answer_comment_id"),
        "question_author": qa_pair.get("question_author"),
        "answer_author": qa_pair.get("answer_author"),
        "answerer_role": qa_pair.get("answerer_role"),
        "artifacts_needed": qa_pair.get("artifacts_needed", []),
        "hard_facts": {
            "cve_ids": hard_facts.get("cve_ids", []),
            "ghsa_ids": hard_facts.get("ghsa_ids", []),
            "cwe_ids": hard_facts.get("cwe_ids", []),
            "osv_ids": hard_facts.get("osv_ids", []),
            "fixed_versions": hard_facts.get("fixed_versions", []),
            "fix_prs": hard_facts.get("fix_prs", []),
            "fix_commits": hard_facts.get("fix_commits", []),
            "advisory_urls": hard_facts.get("advisory_urls", []),
        },
        "comments": clean_comments(qa_pair.get("comments", [])),
        "human_note": verified_entry.get("note", ""),
        "llm_confidence": qa_pair.get("confidence"),
    }
    return record


def build(
    verified_path: Path,
    output_dir: Path,
    output_path: Path,
    status_filter: str,
) -> None:
    with open(verified_path) as f:
        verified_state = json.load(f)

    entries = {k: v for k, v in verified_state.items() if v["status"] == status_filter}
    if not entries:
        print(f"No entries with status='{status_filter}' found.", file=sys.stderr)
        sys.exit(1)

    # Group by repo to load each output folder once
    by_repo: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for key, entry in entries.items():
        parts = key.split("/")
        repo = "/".join(parts[:2])
        by_repo[repo].append((key, entry))

    records = []
    missing_qa = []
    missing_thread = []

    for repo, repo_entries in sorted(by_repo.items()):
        folder = output_dir / repo_to_folder(repo)
        qa_index = load_jsonl_index(folder / "security_qa_pairs.jsonl", "number")
        thread_index = load_jsonl_index(folder / "raw_threads.jsonl", "number")

        for entry_key, verified_entry in repo_entries:
            number = int(entry_key.split("/")[-1])
            qa_pair = qa_index.get(number)
            if qa_pair is None:
                missing_qa.append(entry_key)
                continue
            raw_thread = thread_index.get(number)
            if raw_thread is None:
                missing_thread.append(entry_key)

            records.append(build_record(entry_key, verified_entry, qa_pair, raw_thread))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    print(f"Wrote {len(records)} records → {output_path}")
    if missing_qa:
        print(f"WARNING: {len(missing_qa)} entries had no QA pair: {missing_qa}", file=sys.stderr)
    if missing_thread:
        print(f"WARNING: {len(missing_thread)} entries had no raw thread (labels/reporter missing): {missing_thread}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verified",
        default="security_verified_state.json",
        help="Path to verified state JSON (default: security_verified_state.json)",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Root output directory containing per-repo folders (default: output)",
    )
    parser.add_argument(
        "--output",
        default="dataset/security_benchmark.jsonl",
        help="Destination JSONL file (default: dataset/security_benchmark.jsonl)",
    )
    parser.add_argument(
        "--status",
        default="accepted",
        choices=["accepted", "rejected", "pending"],
        help="Filter entries by verification status (default: accepted)",
    )
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    build(
        verified_path=project_root / args.verified,
        output_dir=project_root / args.output_dir,
        output_path=project_root / args.output,
        status_filter=args.status,
    )


if __name__ == "__main__":
    main()
