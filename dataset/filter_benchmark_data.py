import json

benchmark = "dataset/security_benchmark_v3.jsonl"
open_codes = "dataset/open_codes_verified.json"

with open(open_codes) as f:
    open_codes_set = json.load(f)

benchmark_ids = set()
with open(benchmark) as f:
    benchmark_data = [json.loads(line) for line in f]

    for item in benchmark_data:
        benchmark_ids.add(item["id"])

ids = [id for id in benchmark_ids if not open_codes_set.get(id, {}).get("status") == "rejected"]

with open(benchmark) as f:
    for line in f:
        item = json.loads(line)
        id = item["id"]
        if id in ids:
            # Save to a new jsonl file
            with open("dataset/security_benchmark_filtered.jsonl", "a") as out_f:
                out_f.write(json.dumps(item) + "\n")


# d1 = "dataset/security_benchmark.jsonl"
# d2 = "dataset/security_benchmark_v2.jsonl"

# d1_ids = set()
# with open(d1) as f1:
#     for line in f1:
#         item = json.loads(line)
#         d1_ids.add(item["id"])

# d2_ids = set()
# with open(d2) as f2:
#     for line in f2:
#         item = json.loads(line)
#         id = item["id"]
#         d2_ids.add(id)

# print(f"Total in d1: {len(d1_ids)}")
# print(f"Total in d2: {len(d2_ids)}")
