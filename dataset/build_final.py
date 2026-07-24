"""
Build the final benchmark by joining extraction-level metadata with
normalization-level review decisions:

  dataset/security_benchmark_v2.jsonl  (id)         — hard_facts, artifacts_needed,
                                                        comments, human_note, llm_confidence
  dataset/eval_pairs.jsonl             (thread_id)  — self-contained qa_pairs,
                                                        knowledge_type, grounding_sources

Only threads with approved == true in eval_pairs.jsonl are kept (human-reviewed
in the /normalized UI). Joined on v2.id == eval_pairs.thread_id.

Output: dataset/security_benchmark_final.jsonl
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
BENCHMARK_DATA_PATH = ROOT / "dataset" / "security_benchmark_v3.jsonl"
EVAL_PAIRS_PATH = ROOT / "dataset" / "eval_pairs.jsonl"
OUTPUT_PATH = ROOT / "dataset" / "security_benchmark_final.jsonl"


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def merge(v2_record, eval_record):
    return {
        "id": v2_record["id"],
        "repo": v2_record["repo"],
        "number": v2_record["number"],
        "title": v2_record["title"],
        "url": v2_record["url"],
        "state": v2_record.get("state"),
        "created_at": v2_record.get("created_at"),
        "closed_at": v2_record.get("closed_at"),
        "labels": v2_record.get("labels", []),
        "reporter": v2_record.get("reporter"),
        "security_topic": v2_record.get("security_topic"),
        "qa_summary": v2_record.get("qa_summary"),
        "question_comment_id": v2_record.get("question_comment_id"),
        "answer_comment_id": v2_record.get("answer_comment_id"),
        "question_author": v2_record.get("question_author"),
        "answer_author": v2_record.get("answer_author"),
        "answerer_role": v2_record.get("answerer_role"),
        "artifacts_needed": v2_record.get("artifacts_needed", []),
        "hard_facts": v2_record.get("hard_facts", {}),
        "human_note": v2_record.get("human_note", ""),
        "llm_confidence": v2_record.get("llm_confidence"),
        "comments": v2_record.get("comments", []),
        "qa_pairs": eval_record.get("qa_pairs", []),
        "answer_in_thread_refs": eval_record.get("answer_in_thread_refs", []),
        "leak_flags": eval_record.get("leak_flags", []),
        "normalizer_model": eval_record.get("normalizer_model"),
        "reviewed_at": eval_record.get("reviewed_at"),
        "review_note": eval_record.get("review_note", ""),
    }


def main():
    v2_by_id = {r["id"]: r for r in load_jsonl(BENCHMARK_DATA_PATH)}
    eval_pairs = load_jsonl(EVAL_PAIRS_PATH)
    approved = [r for r in eval_pairs if r.get("approved")]

    records = []
    missing = []
    for eval_record in approved:
        v2_record = v2_by_id.get(eval_record["thread_id"])
        if v2_record is None:
            missing.append(eval_record["thread_id"])
            continue
        records.append(merge(v2_record, eval_record))

    with open(OUTPUT_PATH, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    qa_total = sum(len(r["qa_pairs"]) for r in records)
    print(f"approved threads:  {len(approved)}")
    print(f"merged records:    {len(records)}")
    print(f"merged qa_pairs:   {qa_total}")
    if missing:
        print(f"WARNING: {len(missing)} approved thread_ids had no v2 match: {missing}")
    print(f"-> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
