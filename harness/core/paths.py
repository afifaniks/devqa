"""
SecDevQA harness — canonical filesystem paths.

Every path the harness reads or writes is derived here from one anchor, so module
nesting never has to be reflected in fragile ``Path(__file__).parent.parent`` chains
scattered across the package. Import the constant you need; do not recompute paths.
"""

from __future__ import annotations

from pathlib import Path

# harness/core/paths.py → parents[1] is the harness package dir, parents[2] the repo root.
HARNESS_DIR = Path(__file__).resolve().parents[1]
ROOT = HARNESS_DIR.parent

# ---- project-level data (shared with the benchmark-construction code) -------------
DATASET_DIR = ROOT / "dataset"
MINED_OUTPUT_DIR = ROOT / "output"          # mined corpora: output/<owner>__<repo>/
ADVISORY_DB = ROOT / "advisory-database"     # local github/advisory-database clone

# ---- harness-internal locations ---------------------------------------------------
OUTPUT_DIR = HARNESS_DIR / "output"          # answers_*/grades_*/transcripts/logs
CACHE_DIR = HARNESS_DIR / "cache"            # repo clones, worktrees, advisory + vuln caches
UI_DIR = HARNESS_DIR / "ui"
RESOURCES_DIR = HARNESS_DIR / "resources"
MODELS_CONFIG = RESOURCES_DIR / "models.json"

# ---- benchmark artifacts ----------------------------------------------------------
FINAL_BENCHMARK = DATASET_DIR / "security_benchmark_final.jsonl"
# Released benchmark: accepted-rubric qa_pairs only, rubric embedded
# (dataset/build_release.py). When present it is the single eval source.
RELEASE_BENCHMARK = DATASET_DIR / "security_benchmark_release.jsonl"
