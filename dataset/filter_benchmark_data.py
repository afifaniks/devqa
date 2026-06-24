"""Filter the verified benchmark down to threads whose open codes were NOT rejected.

Input:  dataset/security_benchmark_v3.jsonl  (one thread per line)
        dataset/open_codes_verified.json     (per-id open-coding decisions)
Output: dataset/security_benchmark_filtered.jsonl  (written fresh, deduped by id)
"""
import json

BENCHMARK = "dataset/security_benchmark_v3.jsonl"
OPEN_CODES = "dataset/open_codes_verified.json"
OUTPUT = "dataset/security_benchmark_filtered.jsonl"

with open(OPEN_CODES) as f:
    open_codes_set = json.load(f)

with open(BENCHMARK) as f:
    benchmark_data = [json.loads(line) for line in f if line.strip()]

seen = set()
kept = 0
with open(OUTPUT, "w") as out_f:  # truncate: never append (avoids duplicate lines)
    for item in benchmark_data:
        item_id = item["id"]
        if open_codes_set.get(item_id, {}).get("status") == "rejected":
            continue
        if item_id in seen:  # guard against duplicate ids in the source
            continue
        seen.add(item_id)
        out_f.write(json.dumps(item) + "\n")
        kept += 1

print(f"{len(benchmark_data)} threads in -> {kept} kept (rejected/dup dropped) -> {OUTPUT}")
