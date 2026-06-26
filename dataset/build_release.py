"""
build_release.py — freeze the final released benchmark.

The release benchmark is the subset of security_benchmark_final.jsonl whose grading
rubric has been human-verified and accepted in dataset/rubrics_verified.json. Only
qa_pairs with status == "accepted" survive; the accepted rubric (criteria,
acceptable_alternatives, note) is embedded into the qa_pair so the release file is
self-contained — the harness benchmark page and any grader read the rubric straight
from the qa_pair, no second lookup.

A thread is kept iff at least one of its qa_pairs has an accepted rubric; non-accepted
qa_pairs are dropped from the thread.

Inputs:
  dataset/security_benchmark_final.jsonl   — full normalized benchmark (199 qa_pairs)
  dataset/rubrics_verified.json            — {qid: {rubric, acceptable_alternatives,
                                              note, status}}, keyed by qid

Output:
  dataset/security_benchmark_release.jsonl — accepted-only, rubric embedded

Usage:
  /local/home/amamun/envs/devqa/bin/python dataset/build_release.py
"""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
BENCH_FILE = ROOT / "dataset" / "security_benchmark_final.jsonl"
RUBRIC_FILE = ROOT / "dataset" / "rubrics_verified.json"
RELEASE_FILE = ROOT / "dataset" / "security_benchmark_release.jsonl"


def load_accepted_rubrics() -> dict[str, dict]:
    """qid → embedded rubric payload, for accepted rubrics only."""
    rubrics = json.loads(RUBRIC_FILE.read_text())
    out = {}
    for qid, entry in rubrics.items():
        if entry.get("status") != "accepted":
            continue
        # acceptable_alternatives is authored inconsistently (sometimes a single
        # string, sometimes a list) — normalize to a list of strings.
        alts = entry.get("acceptable_alternatives") or []
        if isinstance(alts, str):
            alts = [alts] if alts.strip() else []
        out[qid] = {
            "rubric": entry.get("rubric") or [],
            "acceptable_alternatives": alts,
            "rubric_note": entry.get("note") or "",
        }
    return out


def build() -> None:
    accepted = load_accepted_rubrics()
    stats = Counter()
    out_lines = []

    with BENCH_FILE.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            thread = json.loads(line)
            if thread.get("error"):
                continue
            kept_pairs = []
            for qa in thread.get("qa_pairs") or []:
                qid = qa.get("qid")
                payload = accepted.get(qid)
                if not payload:
                    stats["qa_dropped"] += 1
                    continue
                qa = {**qa, **payload}  # embed rubric into the qa_pair
                kept_pairs.append(qa)
                stats["qa_kept"] += 1
            if not kept_pairs:
                stats["threads_dropped"] += 1
                continue
            thread = {**thread, "qa_pairs": kept_pairs}
            out_lines.append(json.dumps(thread, ensure_ascii=False))
            stats["threads_kept"] += 1

    RELEASE_FILE.write_text("\n".join(out_lines) + "\n")

    # accepted rubrics that never matched a benchmark qid — surface as a warning
    matched = stats["qa_kept"]
    orphan = len(accepted) - matched
    print(f"accepted rubrics:   {len(accepted)}")
    print(f"qa_pairs kept:      {stats['qa_kept']}")
    print(f"qa_pairs dropped:   {stats['qa_dropped']} (no accepted rubric)")
    print(f"threads kept:       {stats['threads_kept']}")
    print(f"threads dropped:    {stats['threads_dropped']} (no accepted qa_pair)")
    if orphan:
        print(f"WARNING: {orphan} accepted rubric(s) had no matching benchmark qid")
    print(f"\nwrote {RELEASE_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    build()
