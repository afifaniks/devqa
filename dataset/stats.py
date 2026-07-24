"""Stats over dataset/security_benchmark_final.jsonl for the paper
(repo distribution, knowledge_type, answerer_role, artifact and
hard-fact coverage). Run: python dataset/stats.py

security_benchmark_final.jsonl is built by dataset/build_final.py, joining
security_benchmark_v2.jsonl (extraction: hard_facts, artifacts_needed,
comments) with the human-approved subset of eval_pairs.jsonl
(normalization: self-contained qa_pairs, knowledge_type).
"""
import json
import os
from collections import Counter

DATA_PATH = "dataset/security_benchmark_final.jsonl"
OUTPUT_DIR = "output"
VERIFIED_STATE_PATH = "security_verified_state.json"
HARD_FACT_KEYS = [
    "cve_ids", "ghsa_ids", "cwe_ids", "osv_ids",
    "fixed_versions", "fix_prs", "fix_commits", "advisory_urls",
]


def load(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def count_lines(path):
    if not os.path.exists(path):
        return 0
    with open(path) as f:
        return sum(1 for _ in f)


def data_coverage(final_repo_threads):
    """Funnel per repo: security_qa_pairs detected (LLM accept, Stage 1+2)
    -> threads in the final human-approved benchmark."""
    rows = []
    for entry in sorted(os.scandir(OUTPUT_DIR), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        repo = entry.name.replace("__", "/", 1)
        qa = count_lines(os.path.join(entry.path, "security_qa_pairs.jsonl"))
        final = final_repo_threads.get(repo, 0)
        if qa == 0 and final == 0:
            continue
        rows.append((repo, qa, final))

    print("\ndata coverage per repo (detected -> final benchmark)")
    print(f"  {'repo':<32} {'detected':>9} {'final':>6}  yield")
    for repo, qa, final in sorted(rows, key=lambda r: -r[1]):
        yield_pct = f"{100 * final / qa:.1f}%" if qa else "-"
        print(f"  {repo:<32} {qa:>9} {final:>6}  {yield_pct}")
    print(f"  {'TOTAL':<32} {sum(r[1] for r in rows):>9} {sum(r[2] for r in rows):>6}")


def review_date_coverage():
    """Date range (created_at) of threads manually reviewed so far —
    accepted + rejected in security_verified_state.json — per repo."""
    with open(VERIFIED_STATE_PATH) as f:
        state = json.load(f)

    by_repo = {}
    for key, v in state.items():
        if v.get("status") not in ("accepted", "rejected"):
            continue
        parts = key.split("/")
        repo = "/".join(parts[:2])
        number = int(parts[-1])
        by_repo.setdefault(repo, []).append((number, v["status"]))

    print("\nmanual review date range per repo (accepted + rejected)")
    print(f"  {'repo':<32} {'accepted':>8} {'rejected':>8}  {'from':<20} {'to':<20}")
    for repo in sorted(by_repo):
        items = by_repo[repo]
        folder = os.path.join(OUTPUT_DIR, repo.replace("/", "__"))
        created = {}
        for name in ("security_qa_pairs", "raw_threads"):
            path = os.path.join(folder, f"{name}.jsonl")
            if not os.path.exists(path):
                continue
            for line in open(path):
                r = json.loads(line)
                created.setdefault(r["number"], r.get("created_at"))

        dates = sorted(created[n] for n, _ in items if n in created and created[n])
        accepted = sum(1 for _, s in items if s == "accepted")
        rejected = sum(1 for _, s in items if s == "rejected")
        lo, hi = (dates[0], dates[-1]) if dates else ("?", "?")
        print(f"  {repo:<32} {accepted:>8} {rejected:>8}  {lo:<20} {hi:<20}")


def qa_count(records):
    return sum(len(r.get("qa_pairs", [])) for r in records)


def print_counter(title, counter, total=None):
    print(f"\n{title}")
    for key, n in counter.most_common():
        pct = f" ({100 * n / total:.0f}%)" if total else ""
        print(f"  {key:<20} {n}{pct}")


def main():
    records = load(DATA_PATH)

    print("== security_benchmark_final.jsonl ==")
    print(f"threads:  {len(records)}")
    print(f"qa_pairs: {qa_count(records)}")
    print(f"repos:    {len(set(r['repo'] for r in records))}")

    repo_threads = Counter(r["repo"] for r in records)
    repo_qa = Counter()
    for r in records:
        repo_qa[r["repo"]] += len(r.get("qa_pairs", []))

    print("\nper-repo (threads / qa_pairs)")
    for repo, n in repo_threads.most_common():
        print(f"  {repo:<32} {n:>3} / {repo_qa[repo]:>3}")

    knowledge_type = Counter()
    for r in records:
        for qa in r.get("qa_pairs", []):
            knowledge_type[qa.get("knowledge_type")] += 1
    print_counter(
        "knowledge_type (qa_pairs)", knowledge_type,
        total=sum(knowledge_type.values()),
    )

    answerer_role = Counter(r.get("answerer_role") for r in records)
    print_counter("answerer_role (threads)", answerer_role, total=len(records))

    artifacts = Counter()
    for r in records:
        for a in r.get("artifacts_needed", []):
            artifacts[a] += 1
    print_counter(
        "artifacts_needed (threads, multi-label)", artifacts,
        total=len(records),
    )

    hard_fact_threads = Counter()
    hard_fact_totals = Counter()
    for r in records:
        hf = r.get("hard_facts", {})
        for k in HARD_FACT_KEYS:
            vals = hf.get(k) or []
            if vals:
                hard_fact_threads[k] += 1
            hard_fact_totals[k] += len(vals)
    print_counter(
        "hard_facts coverage (threads with >=1)", hard_fact_threads,
        total=len(records),
    )
    print_counter("hard_facts totals (instances)", hard_fact_totals)

    data_coverage(repo_threads)
    review_date_coverage()


if __name__ == "__main__":
    main()
