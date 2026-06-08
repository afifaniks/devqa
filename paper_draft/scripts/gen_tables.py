#!/usr/bin/env python3
"""
gen_tables.py — Regenerate the Benchmark Construction tables and prose numbers
for the SecDevQA paper directly from the data.

Reads:
  dataset/security_benchmark.jsonl     — all mined+extracted Q&A pairs
  dataset/open_codes_verified.json     — human accept/reject + verified open codes
  selection_summary.txt   (optional)   — repo-selection funnel numbers for prose

Writes:
  paper_draft/tables/repo-stats.tex
  paper_draft/tables/artifacts.tex
  paper_draft/tables/axial-categories.tex

Prints the prose numbers used in sections/benchmark-construction.tex so they can
be updated by hand when the corpus changes.

Run:
  /local/home/amamun/envs/devqa/bin/python paper_draft/scripts/gen_tables.py
  # refresh star counts from the GitHub API (needs GITHUB_TOKEN in env/.env):
  /local/home/amamun/envs/devqa/bin/python paper_draft/scripts/gen_tables.py --fetch-stars
"""

import os
import sys
import json
import argparse
import collections
from pathlib import Path

# ── Paths (resolved relative to this file, so cwd does not matter) ────────────
ROOT = Path(__file__).resolve().parents[2]            # repo root
BENCH = ROOT / "dataset" / "security_benchmark.jsonl"
VERIFIED = ROOT / "dataset" / "open_codes_verified.json"
SUMMARY = ROOT / "selection_summary.txt"
TABLES = ROOT / "paper_draft" / "tables"

# ── Static metadata that is not in the data files ────────────────────────────
# Language per repo (GitHub primary language).
LANG = {
    "pyca/cryptography": "Python", "psf/requests": "Python",
    "urllib3/urllib3": "Python", "python-pillow/Pillow": "Python",
    "fastapi/fastapi": "Python", "axios/axios": "JS",
    "expressjs/express": "JS", "stripe/stripe-node": "JS",
    "auth0/node-jsonwebtoken": "JS", "rails/rails": "Ruby",
}
# Last-fetched GitHub star counts (rounded label for the table). Refresh with
# --fetch-stars. Date of this snapshot:
STARS_SNAPSHOT = "2026-06-08"
STARS = {
    "axios/axios": 109092, "expressjs/express": 69126, "psf/requests": 54021,
    "pyca/cryptography": 7612, "python-pillow/Pillow": 13597,
    "urllib3/urllib3": 4028, "stripe/stripe-node": 4434, "rails/rails": 58477,
    "auth0/node-jsonwebtoken": 18173, "fastapi/fastapi": 99025,
}

# Human-readable artifact labels for the artifacts table (key -> label).
ARTIFACT_LABELS = {
    "documentation": "documentation (docs, README, changelog)",
    "code": "code (repository source)",
    "advisory": "advisory (GHSA / OSV / project advisory)",
    "pr_data": r"pr\_data (PR diff or discussion)",
    "issue_tracker": r"issue\_tracker (linked issues)",
    "dependency_manifest": r"dependency\_manifest",
    "external_reference": r"external\_reference (RFC, registry, etc.)",
    "commit_history": r"commit\_history (log, blame, commit)",
    "cve_cwe_db": r"cve\_cwe\_db (NVD/CWE/CVSS)",
    "ci_logs": r"ci\_logs",
}


# ── Axial grouping rules (preliminary, author-proposed) ───────────────────────
# Order matters: first matching bucket wins. Edit these rules as the taxonomy is
# refined. Each code instance lands in exactly one bucket.
AXIAL_RULES = [
    ("Platform and Version Compatibility", [
        "windows python", "unsupported python", "cpython", "type annotation",
        "typescript type", "backward compat", "missing attribute regression",
        "permission denied", "issue tracker", "local version parsing",
        "rat on machine"]),
    ("Dependency and Supply-Chain Security", [
        "transitive", "dependency", "qs ", "npm overrides",
        "compromised package", "typosquat", "prepare script",
        "outdated dependency", "patched dependency"]),
    ("Vulnerability Report Triage", [
        "false positive", "false vulnerability", "scanner", "sca tool",
        "vulnerability database error", "advisory database update",
        "scanner advisory", "cwe report", "critical audit",
        "intermittent vulnerability"]),
    ("Patch, Release, and Compliance", [
        "fixed version", "backport", "security fix", "security release",
        "patched version", "safe version", "version announcement",
        "fix availability", "deprecation support", "dependency version update",
        "pci compliance"]),
    ("TLS and Certificate Validation", [
        # NB: do not add "der" — it is a substring of "header" and would
        # swallow Web codes. DER codes match via "distinguished encoding".
        "cert", "x509", "x.509", "tls", "ssl", "asn.1", "cipher",
        "openssl", "crl", "aki", "authority key", "sni", "hostname",
        "rfc 5280", "rfc5280", "distinguished encoding", "mtls",
        "partial chain", "subject alternative", "pem", "pkcs", "ca bundle",
        "extension semantics", "extension policy", "negotiated group"]),
    ("Cryptographic Key and Algorithm Use", [
        "key ", "rsa", "sm2", "fips", "hash", "digest", "dh param",
        "post-quantum", "pbe", "hsm", "tpm", "encryption algorithm",
        "code signing", "private key", "seed-only", "cryptographic algorithm"]),
    ("HTTP Request and Response Security", [
        "ssrf", "redirect", "header", "cookie", "csrf", "cors", "set-cookie",
        "netrc", "proxy", "request body", "request properties",
        "response buffering", "url scheme", "absolute url", "schemeless",
        "double slash", "dotfiles", "path failure", "retry", "non-idempotent",
        "authorization header", "unexpected authorization", "sql injection",
        "xss", "safe html", "query parsing", "json response", "json middleware",
        "parsed webhook payload"]),
    ("Authentication and Session Integrity", [
        "jwt", "webhook signature", "signature verification", "2fa", "oauth",
        "token", "password reset", "secret", "session", "authenticated endpoint",
        "authorization", "credential leak", "card details", "redaction",
        "code parameter", "wrong secret", "scopes inheritance"]),
    ("Input Handling and Denial of Service", [
        "dos", "redos", "segmentation", "segfault", "crash",
        "memory exhaustion", "crafted input", "font", "libtiff", "psd", "image",
        "null byte", "percent-encode", "malformed", "parsing failure",
        "parsing error", "parsing ambiguity", "regex", "route decode",
        "header parsing", "duplicate font", "array index", "array-valued",
        "boundary generation", "malicious user-provided", "uncaught exception"]),
    ("Concurrency and Data Integrity", [
        "transaction", "thread safety", "data race", "race condition",
        "rollback", "deadlock", "connection release", "global state",
        "shared ssl", "writes outside", "migration data", "foreign key",
        "blob key", "shared block cache"]),
    ("Secure Configuration and Defaults", [
        "middleware", "initializer", "config", "environment variable", "opt-in",
        "rate limit", "android network", "warning suppress", "suppress warning",
        "silent", "deprecat", "side effect", "boot-time", "precompile",
        "default"]),
]


def D(x):
    """Wrap a tweakable numeric value so it renders highlighted via \\dnum in
    the paper (toggle off with \\shownumsfalse in main.tex)."""
    return f"\\dnum{{{x}}}"


def axial_bucket(code: str):
    c = code.lower()
    for name, keys in AXIAL_RULES:
        if any(k in c for k in keys):
            return name
    return None  # unclassified -> reported so rules can be extended


# ── Data loading ──────────────────────────────────────────────────────────────
def load():
    recs = [json.loads(l) for l in open(BENCH) if l.strip()]
    idmap = {r["id"]: r for r in recs}
    ver = json.load(open(VERIFIED))
    accepted, codes_by_pair = [], {}
    for rid, v in ver.items():
        if v.get("status") != "accepted" or rid not in idmap:
            continue
        accepted.append(idmap[rid])
        codes_by_pair[rid] = [c.strip() for c in v.get("codes", [])]
    n_candidates = len(recs)
    n_rejected = sum(1 for v in ver.values() if v.get("status") == "rejected")
    return recs, idmap, accepted, codes_by_pair, n_candidates, n_rejected


def has_hard(r):
    return any(v for v in (r.get("hard_facts") or {}).values())


def stars_label(slug):
    n = STARS.get(slug)
    if n is None:
        return "?"
    return f"{n/1000:.1f}k" if n < 100000 else f"{round(n/1000)}k"


def fetch_stars():
    try:
        import urllib.request
        tok = os.environ.get("GITHUB_TOKEN", "")
        # also try .env
        if not tok and (ROOT / ".env").exists():
            for line in open(ROOT / ".env"):
                if line.startswith("GITHUB_TOKEN"):
                    tok = line.split("=", 1)[1].strip().strip('"')
                    break
        hdr = {"Accept": "application/vnd.github+json"}
        if tok:
            hdr["Authorization"] = f"Bearer {tok}"
        for slug in list(STARS):
            req = urllib.request.Request(
                f"https://api.github.com/repos/{slug}", headers=hdr)
            d = json.load(urllib.request.urlopen(req, timeout=15))
            STARS[slug] = d.get("stargazers_count", STARS[slug])
        print(f"# refreshed stars for {len(STARS)} repos "
              f"(update STARS dict + STARS_SNAPSHOT in this script to persist)")
        for slug, n in STARS.items():
            print(f"#   {slug}: {n}")
    except Exception as e:
        print(f"# star fetch failed ({e}); using embedded values", file=sys.stderr)


# ── Table writers ─────────────────────────────────────────────────────────────
def write_repo_table(accepted):
    acc = collections.Counter(r["repo"] for r in accepted)
    hard = collections.Counter(r["repo"] for r in accepted if has_hard(r))
    repos = sorted(acc, key=lambda s: (-acc[s], -hard[s]))
    total_acc, total_hard = sum(acc.values()), sum(hard.values())
    rows = []
    for s in repos:
        rows.append(f"{s:<25} & {LANG.get(s,'?'):<6} & {D(stars_label(s)):>5} "
                    f"& {D(acc[s])} & {D(hard[s])} \\\\")
    body = "\n".join(rows)
    tex = rf"""\begin{{table}}[t]
\caption{{Repositories in the current SecDevQA corpus. \textbf{{Pairs}} = Q\&A
  pairs retained after manual verification; \textbf{{Hard}} = subset whose answer
  carries at least one externally verifiable fact (CVE/GHSA ID, fixed version,
  fix commit/PR, advisory URL). Stars rounded to thousands ({D(STARS_SNAPSHOT)}).}}
\label{{tab:repos}}
\centering
\footnotesize
\setlength{{\tabcolsep}}{{4pt}}
\begin{{tabular}}{{l l r r r}}
\toprule
\textbf{{Repository}} & \textbf{{Lang.}} & \textbf{{Stars}} & \textbf{{Pairs}} & \textbf{{Hard}} \\
\midrule
{body}
\midrule
\textbf{{Total ({D(len(repos))} repos)}} & & & \textbf{{{D(total_acc)}}} & \textbf{{{D(total_hard)}}} \\
\bottomrule
\end{{tabular}}
\end{{table}}
"""
    (TABLES / "repo-stats.tex").write_text(tex)


def write_artifacts_table(accepted):
    n = len(accepted)
    art = collections.Counter()
    for r in accepted:
        for a in r.get("artifacts_needed", []):
            art[a] += 1
    rows = []
    for a, c in art.most_common():
        label = ARTIFACT_LABELS.get(a, a.replace("_", r"\_"))
        rows.append(f"{label} & {D(c)} & {D(f'{100*c/n:.1f}')} \\\\")
    body = "\n".join(rows)
    tex = rf"""\begin{{table}}[t]
\caption{{Artifact types the maintainer's answer drew on, across the {D(n)}
  verified pairs (a pair may draw on several). Annotations are LLM-extracted and
  spot-checked; they drive the context conditions of the evaluation.}}
\label{{tab:artifacts}}
\centering
\footnotesize
\setlength{{\tabcolsep}}{{5pt}}
\begin{{tabular}}{{l r r}}
\toprule
\textbf{{Artifact type}} & \textbf{{Pairs}} & \textbf{{\%}} \\
\midrule
{body}
\bottomrule
\end{{tabular}}
\end{{table}}
"""
    (TABLES / "artifacts.tex").write_text(tex)


def write_axial_table(accepted, codes_by_pair):
    n = len(accepted)
    pairs_in = collections.defaultdict(set)
    examples = collections.defaultdict(collections.Counter)
    unclassified = []
    for rid, codes in codes_by_pair.items():
        for code in codes:
            b = axial_bucket(code)
            if b is None:
                unclassified.append(code)
                continue
            pairs_in[b].add(rid)
            examples[b][code] += 1
    order = sorted(pairs_in, key=lambda b: -len(pairs_in[b]))
    rows = []
    for b in order:
        ex = ", ".join(c for c, _ in examples[b].most_common(6))
        rows.append(f"{b} & {D(len(pairs_in[b]))} & {ex} \\\\")
    body = "\n".join(rows)
    tex = rf"""\begin{{table*}}[t]
\caption{{\emph{{Preliminary, author-proposed}} axial grouping of the open
  codes into candidate higher-level categories. \textbf{{Pairs}} counts verified
  pairs touching the category (a two-code pair may fall in two categories, so
  the column sums to more than {D(n)}). This grouping is a working draft to be
  finalized by axial coding with an independent second coder and inter-rater
  agreement; category names and boundaries are not yet fixed.}}
\label{{tab:axial}}
\centering
\footnotesize
\begin{{tabular}}{{l r p{{0.62\linewidth}}}}
\toprule
\textbf{{Candidate category}} & \textbf{{Pairs}} & \textbf{{Representative open codes}} \\
\midrule
{body}
\bottomrule
\end{{tabular}}
\end{{table*}}
"""
    (TABLES / "axial-categories.tex").write_text(tex)
    if unclassified:
        print(f"\n# WARNING: {len(unclassified)} code instance(s) hit no axial "
              f"rule — extend AXIAL_RULES:")
        for c in sorted(set(unclassified)):
            print(f"#   {c}")


# small helper so write_repo_table can re-read raw recs for mined counts
_RAW = None
def load_all_recs():
    global _RAW
    if _RAW is None:
        _RAW = [json.loads(l) for l in open(BENCH) if l.strip()]
    return _RAW


# ── Prose numbers ─────────────────────────────────────────────────────────────
def print_prose(recs, accepted, codes_by_pair, n_candidates, n_rejected):
    n = len(accepted)
    hard = [r for r in accepted if has_hard(r)]
    role = collections.Counter(r.get("answerer_role") for r in accepted)
    langs = collections.Counter(LANG.get(r["repo"], "?") for r in accepted)
    repos = collections.Counter(r["repo"] for r in accepted)
    hf = collections.Counter()
    for r in hard:
        for k, v in (r.get("hard_facts") or {}).items():
            if v:
                hf[k] += 1
    n_codes = sum(len(c) for c in codes_by_pair.values())
    uniq = len({c.lower() for cs in codes_by_pair.values() for c in cs})
    cl = sorted(len(r.get("comments", [])) for r in accepted)
    med = cl[len(cl)//2]
    yrs = sorted({(r.get("created_at") or "")[:4] for r in accepted})
    top_repo, top_n = repos.most_common(1)[0]

    print("\n" + "="*60)
    print("PROSE NUMBERS for sections/benchmark-construction.tex")
    print("="*60)
    if SUMMARY.exists():
        print("\n[selection funnel — from selection_summary.txt]")
        for line in SUMMARY.read_text().splitlines():
            if any(t in line for t in ("snapshot", "Unique repos", "advisory filter",
                    "passing all filters", "selected", "Ecosystems")):
                print("   " + line.strip())
    print(f"\n[corpus]  candidates extracted : {n_candidates}")
    print(f"          accepted (verified)  : {n} ({100*n/n_candidates:.1f}%)")
    print(f"          rejected             : {n_rejected}")
    print(f"          hard-verifiable      : {len(hard)} ({100*len(hard)/n:.1f}% of accepted)")
    print(f"          repos / languages    : {len(repos)} / {dict(langs)}")
    print(f"          largest repo share   : {top_repo} {top_n} "
          f"({100*top_n/n:.1f}%)")
    print(f"          answerer roles       : {dict(role)}")
    print(f"          thread years         : {yrs[0]}-{yrs[-1]}")
    print(f"          comments/thread      : median {med}, "
          f"mean {sum(cl)/len(cl):.1f}, max {cl[-1]}")
    print(f"\n[hard facts over {len(hard)} hard pairs]")
    for k, c in hf.most_common():
        print(f"          {k:<16}: {c}")
    print(f"\n[open coding]  code instances : {n_codes}  "
          f"distinct : {uniq}  pairs : {n}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch-stars", action="store_true",
                    help="refresh star counts from the GitHub API")
    args = ap.parse_args()
    if args.fetch_stars:
        fetch_stars()
    recs, idmap, accepted, codes_by_pair, n_cand, n_rej = load()
    write_repo_table(accepted)
    write_artifacts_table(accepted)
    write_axial_table(accepted, codes_by_pair)
    print(f"Wrote {TABLES}/repo-stats.tex, artifacts.tex, axial-categories.tex")
    print_prose(recs, accepted, codes_by_pair, n_cand, n_rej)


if __name__ == "__main__":
    main()
