"""
build_release.py — freeze the final released benchmark.

The release benchmark is the subset of security_benchmark_final.jsonl whose grading
rubric has been human-verified and accepted by the release reviewer. Only qa_pairs with
status == "accepted" survive; the accepted rubric (criteria, acceptable_alternatives,
note) is embedded into the qa_pair so the release file is self-contained — the harness
benchmark page and any grader read the rubric straight from the qa_pair, no second
lookup.

A thread is kept iff at least one of its qa_pairs has an accepted rubric; non-accepted
qa_pairs are dropped from the thread.

Rubrics come from the reviewer's own file, dataset/reviews/<reviewer>.json — the single
source, and where review_ui writes every rubric edit. Other reviewers' files are for
inter-rater agreement (dataset/agreement.py), not for the release: only the named
release reviewer decides what ships. (The pre-reviewer shared overlay
dataset/rubrics_verified.json was migrated into afif.json and is no longer read.)

Inputs:
  dataset/security_benchmark_final.jsonl   — full normalized benchmark
  dataset/reviews/<reviewer>.json          — {record_id: {rubrics: {qid: {rubric,
                                              acceptable_alternatives, note, status}}}}

Output:
  dataset/security_benchmark_release.jsonl — accepted-only, rubric embedded

Usage:
  /local/home/amamun/envs/devqa/bin/python dataset/build_release.py
  /local/home/amamun/envs/devqa/bin/python dataset/build_release.py --reviewer afif
"""

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
BENCH_FILE = ROOT / "dataset" / "security_benchmark_final.jsonl"
REVIEWS_DIR = ROOT / "dataset" / "reviews"
RELEASE_FILE = ROOT / "dataset" / "security_benchmark_release.jsonl"
DEFAULT_REVIEWER = "afif"


def _payload(entry: dict) -> dict:
    # acceptable_alternatives is authored inconsistently (sometimes a single
    # string, sometimes a list) — normalize to a list of strings.
    alts = entry.get("acceptable_alternatives") or []
    if isinstance(alts, str):
        alts = [alts] if alts.strip() else []
    return {
        "rubric": entry.get("rubric") or [],
        "acceptable_alternatives": alts,
        "rubric_note": entry.get("note") or "",
    }


def load_accepted_rubrics(reviewer: str) -> tuple[dict[str, dict], Counter]:
    """qid → embedded rubric payload, for accepted rubrics only."""
    review_file = REVIEWS_DIR / f"{reviewer}.json"
    if not review_file.exists():
        raise SystemExit(
            f"no review file {review_file.relative_to(ROOT)} — review on "
            f"/benchmark?reviewer={reviewer}, or pass --reviewer")

    raw: dict[str, dict] = {}
    for record in json.loads(review_file.read_text()).values():
        raw.update(record.get("rubrics") or {})

    out = {qid: _payload(e) for qid, e in raw.items() if e.get("status") == "accepted"}
    src = Counter({"accepted": len(out), "not_accepted": len(raw) - len(out)})
    return out, src


def build(reviewer: str) -> None:
    accepted, src = load_accepted_rubrics(reviewer)
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
    print(f"reviewer:           {reviewer}")
    print(f"accepted rubrics:   {len(accepted)} ({src['not_accepted']} not accepted)")
    print(f"qa_pairs kept:      {stats['qa_kept']}")
    print(f"qa_pairs dropped:   {stats['qa_dropped']} (no accepted rubric)")
    print(f"threads kept:       {stats['threads_kept']}")
    print(f"threads dropped:    {stats['threads_dropped']} (no accepted qa_pair)")
    if orphan:
        print(f"WARNING: {orphan} accepted rubric(s) had no matching benchmark qid")
    print(f"\nwrote {RELEASE_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reviewer", default=DEFAULT_REVIEWER,
                    help="whose dataset/reviews/<id>.json decides the release "
                         f"(default: {DEFAULT_REVIEWER})")
    build(ap.parse_args().reviewer)
