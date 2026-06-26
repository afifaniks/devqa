#!/usr/bin/env python3
"""Inter-rater agreement across the multi-reviewer benchmark review (review_ui /benchmark).

Each reviewer edits /benchmark with ?reviewer=<id>; their edits land in their OWN file,
dataset/reviews/<id>.json:

    { "<record_id>": { "fields": {...}, "rubrics": {qid:{...}}, "reviewer": id, ... } }

This script reads every reviewer file plus the base benchmark, computes each reviewer's
EFFECTIVE value per dimension (their edit if present, else the anchored base value they
left as-is), and reports Fleiss' kappa + percent agreement per dimension, with a
per-record/qid disagreement report for adjudication.

  python dataset/agreement.py
  python dataset/agreement.py --reviewers R1,R2,R3
  python dataset/agreement.py --out dataset/agreement_report.json

Only records reviewed (present) by ALL included reviewers count toward a dimension
(complete cases); coverage is reported.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEWS_DIR = ROOT / "dataset" / "reviews"
BENCH_FINAL = ROOT / "dataset" / "security_benchmark_final.jsonl"
BENCH_LEGACY = ROOT / "dataset" / "security_benchmark.jsonl"

ARTIFACTS = ["code", "documentation", "cve_cwe_db", "pr_data", "dependency_manifest",
             "external_reference", "commit_history", "advisory", "issue_tracker"]


def load_jsonl(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def fleiss_kappa(rows):
    """rows[i] = category counts for subject i (each sums to rater count n)."""
    rows = [r for r in rows if sum(r) >= 2]
    if not rows:
        return None
    n = sum(rows[0])
    if any(sum(r) != n for r in rows):
        return None  # ragged rater counts — undefined
    N, k = len(rows), len(rows[0])
    p_j = [sum(rows[i][j] for i in range(N)) / (N * n) for j in range(k)]
    Pe = sum(p * p for p in p_j)
    P_i = [(sum(c * c for c in rows[i]) - n) / (n * (n - 1)) for i in range(N)]
    Pbar = sum(P_i) / N
    return 1.0 if abs(1 - Pe) < 1e-12 else (Pbar - Pe) / (1 - Pe)


def counts(values, cats):
    row = [0] * len(cats)
    for v in values:
        row[cats.index(v)] += 1
    return row


def categorical(units, rv_ids, label):
    """units: list of (key, {reviewer: value}); skip a unit if any reviewer value is None."""
    cats, rows, dis = [], [], []
    for key, vals in units:
        vs = [vals.get(r) for r in rv_ids]
        if any(v is None for v in vs):
            continue
        for v in vs:
            if v not in cats:
                cats.append(v)
        rows.append(counts(vs, cats))
        if len(set(vs)) > 1:
            dis.append({"unit": key, **{r: vals.get(r) for r in rv_ids}})
    rows = [r + [0] * (len(cats) - len(r)) for r in rows]
    n = len(rows)
    return {"label": label, "n": n, "pct_agreement": (n - len(dis)) / n if n else None,
            "fleiss_kappa": fleiss_kappa(rows), "categories": cats, "disagreements": dis}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviewers", default="")
    ap.add_argument("--out", type=Path, default=ROOT / "dataset" / "agreement_report.json")
    args = ap.parse_args()

    files = sorted(REVIEWS_DIR.glob("*.json")) if REVIEWS_DIR.exists() else []
    if not files:
        raise SystemExit(f"no reviewer files in {REVIEWS_DIR} — review on /benchmark?reviewer=…")
    only = {r.strip() for r in args.reviewers.split(",") if r.strip()}
    reviews = {p.stem: json.loads(p.read_text(encoding="utf-8"))
               for p in files if (not only or p.stem in only)}
    rv_ids = list(reviews)
    if len(rv_ids) < 2:
        raise SystemExit(f"need ≥2 reviewer files in {REVIEWS_DIR} (have {rv_ids})")

    bench = load_jsonl(BENCH_FINAL if BENCH_FINAL.exists() else BENCH_LEGACY)
    base = {r["id"]: r for r in bench}
    base_kt = {p["qid"]: p.get("knowledge_type")
               for r in bench for p in (r.get("qa_pairs") or []) if p.get("qid")}

    # records reviewed (present) by every included reviewer
    common = set.intersection(*[set(reviews[r].keys()) for r in rv_ids])
    coverage = {r: len(reviews[r]) for r in rv_ids}
    print(f"Reviewers: {', '.join(f'{r}({coverage[r]} reviewed)' for r in rv_ids)}")
    print(f"Records reviewed by all {len(rv_ids)}: {len(common)}\n")

    def fields(r, rid):
        return (reviews[r].get(rid) or {}).get("fields") or {}

    def eff_role(r, rid):
        return fields(r, rid).get("answerer_role") or base.get(rid, {}).get("answerer_role")

    def eff_rescase(r, rid):
        return fields(r, rid).get("resolution_case") or base.get(rid, {}).get("resolution_case")

    def eff_artifacts(r, rid):
        return fields(r, rid).get("artifacts_needed") or base.get(rid, {}).get("artifacts_needed") or []

    def eff_kt(r, rid, qid):
        for p in fields(r, rid).get("qa_pairs") or []:
            if p.get("qid") == qid and p.get("knowledge_type"):
                return p["knowledge_type"]
        return base_kt.get(qid)

    def eff_rubric_status(r, rid, qid):
        return ((reviews[r].get(rid) or {}).get("rubrics") or {}).get(qid, {}).get("status")

    report = {"reviewers": rv_ids, "coverage": coverage,
              "n_common_records": len(common), "dimensions": {}}

    # answerer_role (record-level)
    role_units = [(rid, {r: eff_role(r, rid) for r in rv_ids}) for rid in sorted(common)]
    report["dimensions"]["answerer_role"] = categorical(role_units, rv_ids, "answerer_role")

    # resolution_case (record-level): fix_before / fix_after / explanation_only / undetermined
    res_units = [(rid, {r: eff_rescase(r, rid) for r in rv_ids}) for rid in sorted(common)]
    report["dimensions"]["resolution_case"] = categorical(res_units, rv_ids, "resolution_case")

    # knowledge_type (per qa_pair within reviewed records)
    kt_units = []
    for rid in sorted(common):
        for p in base.get(rid, {}).get("qa_pairs") or []:
            qid = p.get("qid")
            if qid:
                kt_units.append((qid, {r: eff_kt(r, rid, qid) for r in rv_ids}))
    report["dimensions"]["knowledge_type"] = categorical(kt_units, rv_ids, "knowledge_type")

    # rubric verify status (per qid) — only where ≥1 reviewer rated it
    rub_units = []
    for rid in sorted(common):
        for p in base.get(rid, {}).get("qa_pairs") or []:
            qid = p.get("qid")
            if not qid:
                continue
            vals = {r: eff_rubric_status(r, rid, qid) for r in rv_ids}
            if any(v for v in vals.values()):
                rub_units.append((qid, {r: vals[r] or "unrated" for r in rv_ids}))
    report["dimensions"]["rubric_status"] = categorical(rub_units, rv_ids, "rubric_status")

    # artifacts_needed (multilabel → per-artifact binary κ)
    per_art, art_dis = {}, []
    for art in ARTIFACTS:
        rows = []
        for rid in sorted(common):
            present = [art in eff_artifacts(r, rid) for r in rv_ids]
            rows.append([sum(present), len(present) - sum(present)])
        per_art[art] = fleiss_kappa(rows)
    for rid in sorted(common):
        sets = {r: set(eff_artifacts(r, rid)) for r in rv_ids}
        u = set().union(*sets.values())
        i = set.intersection(*sets.values()) if sets else set()
        if u - i:
            art_dis.append({"unit": rid, **{r: sorted(sets[r]) for r in rv_ids}})
    ks = [v for v in per_art.values() if v is not None]
    report["dimensions"]["artifacts_needed"] = {
        "label": "artifacts_needed", "n": len(common),
        "mean_fleiss_kappa": sum(ks) / len(ks) if ks else None,
        "per_artifact_kappa": per_art, "disagreements": art_dis}

    # ── print table ──
    def fmt(x):
        return "—" if x is None else f"{x:.3f}"
    print(f"{'dimension':<26} {'n':>5} {'%agree':>8} {'kappa':>8}")
    print("-" * 50)
    for key in ("answerer_role", "resolution_case", "knowledge_type", "rubric_status"):
        d = report["dimensions"][key]
        pa = "—" if d["pct_agreement"] is None else f"{100*d['pct_agreement']:.1f}%"
        print(f"{d['label']:<26} {d['n']:>5} {pa:>8} {fmt(d['fleiss_kappa']):>8}")
    a = report["dimensions"]["artifacts_needed"]
    print(f"{'artifacts_needed (mean)':<26} {a['n']:>5} {'—':>8} {fmt(a['mean_fleiss_kappa']):>8}")

    n_dis = sum(len(d.get("disagreements", [])) for d in report["dimensions"].values())
    print(f"\nDisagreements flagged: {n_dis}")
    print("Note: free-text fields (qa_summary, security_topic) are not κ-scored.")
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Report: {args.out}")


if __name__ == "__main__":
    main()
