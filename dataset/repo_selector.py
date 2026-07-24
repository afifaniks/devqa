#!/usr/bin/env python3
"""
select_repos.py — Systematic repository selection for SecDevQA.

Starting universe: the complete GitHub Advisory Database
(https://github.com/github/advisory-database), cloned locally.
Every GHSA entry is parsed; all referenced GitHub repositories are extracted.
A three-criteria filter is then applied to this exhaustive universe:

  1. ≥ MIN_FIXED_ADVISORIES GHSA advisories with a documented fix version
  2. ≥ MIN_STARS GitHub stars
  3. Last push within MAX_MONTHS_SINCE_PUSH months (active maintenance)

Repos are ranked by fixed-advisory count descending within each ecosystem;
top-K per ecosystem are selected to ensure language/domain diversity.

Output:
  repo_candidates.csv   — all repos passing the filter, ranked
  selection_summary.txt — snapshot metadata for the paper methods section

Usage:
    # Step 1: clone the advisory database (once)
    git clone --depth=1 https://github.com/github/advisory-database advisory-database

    # Step 2: install deps and run
    pip install requests --break-system-packages
    export GITHUB_TOKEN=ghp_...
    python select_repos.py --advisory-db ./advisory-database

    # Custom thresholds
    python select_repos.py --advisory-db ./advisory-database \\
        --min-fixed-advisories 10 --min-stars 1000 \\
        --max-months-since-push 24 --top-per-ecosystem 5
"""

import os
import csv
import json
import time
import argparse
import subprocess
import requests
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

from dotenv import load_dotenv


load_dotenv()


# ── Ecosystem mapping ─────────────────────────────────────────────────────────
# GHSA ecosystem strings → canonical names used in output
ECOSYSTEM_MAP = {
    "npm":        "npm",
    "pip":        "PyPI",
    "maven":      "Maven",
    "go":         "Go",
    "rubygems":   "RubyGems",
    "crates.io":  "crates.io",
    "nuget":      "NuGet",
    "composer":   "Composer",
    "pub":        "Dart/pub",
    "hex":        "Elixir/hex",
    "erlang":     "Erlang",
    "actions":    "GitHub Actions",
    "swift":      "Swift",
}


# ── GHSA database parsing ─────────────────────────────────────────────────────

def get_db_snapshot_date(advisory_db_path: Path) -> str:
    """Return the HEAD commit date of the advisory-database clone."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ci"],
            cwd=advisory_db_path, capture_output=True, text=True
        )
        return result.stdout.strip()[:10]  # YYYY-MM-DD
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def parse_advisory_db(advisory_db_path: Path) -> dict[str, dict]:
    """
    Walk the advisory-database directory, parse every GHSA JSON file,
    and accumulate per-repo statistics.

    Returns:
        repo_data: {
            "owner/repo": {
                "total_ghsa": int,
                "fixed_ghsa": int,
                "ecosystems": set,
                "packages": set,
                "ghsa_ids": list,
            }
        }
    """
    repo_data: dict[str, dict] = {}
    n_parsed = 0
    n_skipped = 0

    # Advisory files live under advisories/github-reviewed/**/*.json
    reviewed_dir = advisory_db_path / "advisories" / "github-reviewed"
    if not reviewed_dir.exists():
        # Fallback: search entire tree
        reviewed_dir = advisory_db_path

    for json_file in reviewed_dir.rglob("*.json"):
        try:
            with open(json_file, encoding="utf-8") as f:
                adv = json.load(f)
        except Exception:
            n_skipped += 1
            continue

        ghsa_id = adv.get("id", "")
        if not ghsa_id.startswith("GHSA-"):
            n_skipped += 1
            continue

        # Extract fix version presence
        has_fix = False
        ecosystems_in_adv = set()
        packages_in_adv = set()

        for affected in adv.get("affected", []):
            pkg = affected.get("package", {})
            eco = pkg.get("ecosystem", "").lower()
            pkg_name = pkg.get("name", "")
            if eco:
                ecosystems_in_adv.add(ECOSYSTEM_MAP.get(eco, eco))
            if pkg_name:
                packages_in_adv.add(pkg_name)

            for rng in affected.get("ranges", []):
                for evt in rng.get("events", []):
                    if "fixed" in evt:
                        has_fix = True

        # Extract referenced GitHub repos from the references list
        refs = adv.get("references", [])
        repos_in_adv = set()
        for ref in refs:
            url = ref.get("url", "")
            if "github.com/" not in url:
                continue
            # Normalise: strip protocol, split on /
            path = url.replace("https://github.com/", "").replace(
                "http://github.com/", ""
            )
            parts = path.split("/")
            if len(parts) < 2:
                continue
            owner = parts[0]
            repo = parts[1].split("#")[0].split("?")[0].rstrip("/")
            # Skip non-repo paths (e.g. github.com/advisories/...)
            if not owner or not repo or owner in ("advisories", "security"):
                continue
            # Skip obvious non-code repos
            if repo.lower() in ("", "issues", "pulls", "releases"):
                continue
            slug = f"{owner}/{repo}"
            repos_in_adv.add(slug)

        for slug in repos_in_adv:
            if slug not in repo_data:
                repo_data[slug] = {
                    "total_ghsa": 0,
                    "fixed_ghsa": 0,
                    "ecosystems": set(),
                    "packages": set(),
                    "ghsa_ids": [],
                }
            repo_data[slug]["total_ghsa"] += 1
            if has_fix:
                repo_data[slug]["fixed_ghsa"] += 1
            repo_data[slug]["ecosystems"].update(ecosystems_in_adv)
            repo_data[slug]["packages"].update(packages_in_adv)
            repo_data[slug]["ghsa_ids"].append(ghsa_id)

        n_parsed += 1

    print(f"  Parsed {n_parsed:,} GHSA advisories, skipped {n_skipped}")
    print(f"  Unique GitHub repos referenced: {len(repo_data):,}")
    return repo_data


# ── GitHub API helpers ────────────────────────────────────────────────────────

def github_headers() -> dict:
    h = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def github_repo_info(owner: str, repo: str) -> dict | None:
    """Fetch stars, language, archived flag, and last push date."""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        r = requests.get(url, headers=github_headers(), timeout=15)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        d = r.json()
        return {
            "stars":     d.get("stargazers_count", 0),
            "archived":  d.get("archived", False),
            "language":  d.get("language", ""),
            "pushed_at": d.get("pushed_at", ""),
        }
    except Exception as e:
        print(f"    GitHub API error for {owner}/{repo}: {e}")
        return None


def months_since(iso_timestamp: str) -> float | None:
    if not iso_timestamp:
        return None
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days / 30.44
    except Exception:
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select SecDevQA repositories from the full GHSA advisory database."
    )
    parser.add_argument("--advisory-db", default="./advisory-database",
                        help="Path to cloned github/advisory-database (default: ./advisory-database)")
    parser.add_argument("--min-fixed-advisories", type=int, default=10,
                        help="Min GHSA advisories with a fix version (default 10)")
    parser.add_argument("--min-stars", type=int, default=1000,
                        help="Min GitHub stars (default 1000)")
    parser.add_argument("--max-months-since-push", type=int, default=24,
                        help="Max months since last push (default 24)")
    parser.add_argument("--top-per-ecosystem", type=int, default=5,
                        help="Max repos selected per ecosystem (default 5)")
    parser.add_argument("--output-csv", default="repo_candidates.csv")
    parser.add_argument("--output-summary", default="selection_summary.txt")
    args = parser.parse_args()

    advisory_db_path = Path(args.advisory_db)
    if not advisory_db_path.exists():
        print(f"ERROR: advisory database not found at {advisory_db_path}")
        print("Clone it first:")
        print("  git clone --depth=1 https://github.com/github/advisory-database advisory-database")
        return

    # ── Step 1: Parse the full advisory database ──────────────────────────────
    snapshot_date = get_db_snapshot_date(advisory_db_path)
    print(f"Step 1: Parsing advisory database (snapshot: {snapshot_date})...")
    repo_data = parse_advisory_db(advisory_db_path)

    # ── Step 2: Apply advisory count filter ───────────────────────────────────
    print(f"\nStep 2: Applying advisory filter (fixed_ghsa ≥ {args.min_fixed_advisories})...")
    filtered = {
        slug: d for slug, d in repo_data.items()
        if d["fixed_ghsa"] >= args.min_fixed_advisories
    }
    print(f"  Repos passing advisory filter: {len(filtered):,}")

    # ── Step 3: Enrich with GitHub metadata and apply remaining filters ────────
    print(f"\nStep 3: Fetching GitHub metadata and applying star / activity filters...")
    if not os.environ.get("GITHUB_TOKEN"):
        print("  WARNING: GITHUB_TOKEN not set — unauthenticated rate limit is 60 req/hr.")

    enriched = []
    n_not_found = n_archived = n_stars = n_stale = 0

    for i, (slug, d) in enumerate(sorted(
        filtered.items(), key=lambda x: -x[1]["fixed_ghsa"]
    )):
        owner, repo = slug.split("/", 1)

        # Progress indicator every 50 repos
        if i % 50 == 0:
            print(f"  [{i}/{len(filtered)}] processing...")

        info = github_repo_info(owner, repo)
        time.sleep(0.5)

        if info is None:
            n_not_found += 1
            continue
        if info["archived"]:
            n_archived += 1
            continue
        if info["stars"] < args.min_stars:
            n_stars += 1
            continue

        age = months_since(info["pushed_at"])
        if age is None or age > args.max_months_since_push:
            n_stale += 1
            continue

        enriched.append({
            "repo":               slug,
            "ecosystem":          ", ".join(sorted(d["ecosystems"])) or "unknown",
            "language":           info["language"],
            "stars":              info["stars"],
            "months_since_push":  round(age, 1),
            "total_ghsa":         d["total_ghsa"],
            "fixed_ghsa":         d["fixed_ghsa"],
            "fix_coverage_pct":   round(100 * d["fixed_ghsa"] / max(d["total_ghsa"], 1)),
            "packages":           ", ".join(sorted(d["packages"]))[:200],
        })

    print(f"\n  Results:")
    print(f"    Not found / private:  {n_not_found:,}")
    print(f"    Archived:             {n_archived:,}")
    print(f"    Below star threshold: {n_stars:,}")
    print(f"    Stale (>{args.max_months_since_push}mo): {n_stale:,}")
    print(f"    Passing all filters:  {len(enriched):,}")

    # ── Step 4: Rank and select top-K per ecosystem ───────────────────────────
    print(f"\nStep 4: Selecting top {args.top_per_ecosystem} per ecosystem by fixed_ghsa...")

    by_ecosystem = defaultdict(list)
    for r in enriched:
        # Use primary ecosystem (first listed) for grouping
        primary_eco = r["ecosystem"].split(",")[0].strip()
        by_ecosystem[primary_eco].append(r)

    selected = []
    for eco, repos in sorted(by_ecosystem.items()):
        ranked = sorted(repos, key=lambda x: x["fixed_ghsa"], reverse=True)
        top = ranked[:args.top_per_ecosystem]
        selected.extend(top)
        print(f"\n  [{eco}] — {len(top)} selected from {len(repos)} candidates")
        for r in top:
            print(f"    {r['repo']:<50} fixed={r['fixed_ghsa']:>4}  stars={r['stars']:>7,}")

    # ── Step 5: Write outputs ─────────────────────────────────────────────────
    fieldnames = [
        "repo", "ecosystem", "language", "stars", "months_since_push",
        "total_ghsa", "fixed_ghsa", "fix_coverage_pct", "packages",
    ]
    with open(args.output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted(enriched, key=lambda x: x["fixed_ghsa"], reverse=True):
            writer.writerow(row)

    # Summary for paper methods section
    summary_lines = [
        f"SecDevQA Repository Selection Summary",
        f"======================================",
        f"Advisory database snapshot date : {snapshot_date}",
        f"Total GHSA advisories parsed    : (see parse output)",
        f"Unique repos in advisory DB     : {len(repo_data):,}",
        f"",
        f"Filter criteria (pre-specified):",
        f"  1. fixed_ghsa >= {args.min_fixed_advisories}",
        f"  2. GitHub stars >= {args.min_stars:,}",
        f"  3. Last push within {args.max_months_since_push} months",
        f"",
        f"Repos after advisory filter     : {len(filtered):,}",
        f"Repos passing all filters       : {len(enriched):,}",
        f"Repos selected (top-{args.top_per_ecosystem}/ecosystem)  : {len(selected):,}",
        f"Ecosystems represented          : {len(by_ecosystem):,}",
        f"",
        f"Selected repositories:",
    ]
    for r in sorted(selected, key=lambda x: x["fixed_ghsa"], reverse=True):
        summary_lines.append(
            f"  {r['repo']:<50} ecosystem={r['ecosystem']:<12} "
            f"fixed_ghsa={r['fixed_ghsa']:>4}  stars={r['stars']:>7,}"
        )

    with open(args.output_summary, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines) + "\n")

    print(f"\nWrote {len(enriched)} candidates → {args.output_csv}")
    print(f"Wrote selection summary → {args.output_summary}")
    print(f"\nTotal selected: {len(selected)} repos across {len(by_ecosystem)} ecosystems")


if __name__ == "__main__":
    main()