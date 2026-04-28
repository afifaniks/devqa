import json
import os
from config import OUTPUT_DIR


def repo_dir(repo: str) -> str:
    """Returns the output directory for a repo, creating it if needed."""
    safe = repo.replace("/", "__")
    path = os.path.join(OUTPUT_DIR, safe)
    os.makedirs(path, exist_ok=True)
    return path


def save_jsonl(repo: str, name: str, records: list):
    """Write a list of dicts to a .jsonl file."""
    path = os.path.join(repo_dir(repo), f"{name}.jsonl")
    with open(path, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    print(f"  saved {len(records)} records → {path}")


def load_jsonl(repo: str, name: str) -> list:
    """Read a .jsonl file back into a list of dicts."""
    path = os.path.join(repo_dir(repo), f"{name}.jsonl")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def already_mined(repo: str, name: str) -> bool:
    """Check if a file has already been mined (skip re-mining)."""
    path = os.path.join(repo_dir(repo), f"{name}.jsonl")
    return os.path.exists(path) and os.path.getsize(path) > 0
