"""
Security-focused Q&A detection pipeline (Track B — security scope).

Mines real developer SECURITY information needs from public OSS threads.
No keyword pre-filter — the LLM decides what counts as security. The only
Stage-0 pre-filter is the sanity check that the thread has substantive
non-bot participation.

Stage 1   (LLM, N-sample self-consistency):
          Detect whether the thread contains a valid security-related
          developer information need. Emits free-text need_summary — no
          fixed enum, for later open + axial coding into the security
          taxonomy. Tightened with explicit BAD-pattern guardrails
          (PEM-format usage errors, browser-storage deflections,
          adapter/config Qs with no risk angle, wrong-forum deflections).

Stage 1.5 (regex):
          Extract candidate hard-fact tokens (CVE/GHSA/CWE/OSV IDs,
          version numbers, PR refs, commit SHAs, advisory URLs) with
          comment-ID provenance and surrounding text. The LLM in Stage 2
          assigns each candidate a semantic role (subject, fixed_version,
          affected_version, fix_pr, fix_commit, advisory_url, unrelated).

Stage 2   (LLM):
          Extract verbatim Q, verbatim A, artifacts_needed, structured
          hard_facts (the deterministic grading anchors), free-text
          security_topic phrase, and answerer_role (including op_self
          when OP self-answers).

Acceptance gate (every accepted pair must be verifiable in principle):
  - answer < 30 chars                                       → drop
  - no hard_facts AND artifacts_needed in ([] | ["none"])   → drop (no anchor)
  - 30 <= answer < 100 chars AND no hard_facts              → drop (thin source-only)
  - otherwise                                               → accept

Grading downstream:
  - hard_facts populated     → deterministic grade (identifier match)
  - else artifacts non-empty → source-anchored judge against cited artifacts

Output: output/<owner>__<repo>/security_qa_pairs.jsonl

Usage:
  python detect_security_qa.py --repo psf/requests
  python detect_security_qa.py --repo psf/requests --limit 500
  python detect_security_qa.py --repo psf/requests --max-pairs 50 --force
  python detect_security_qa.py --repo psf/requests --stage1-samples 1   # disable self-consistency
"""

import argparse
import os
import re
import sys

from tqdm import tqdm

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import REPOS
from utils.ollama_client import STAGE1_MODEL, generate_json, is_running
from utils.storage import (append_record, load_checkpoint, load_jsonl,
                           save_checkpoint)

SYSTEM_PROMPT = """You are a research assistant analyzing GitHub threads
for an academic study on real developer security information needs in
open-source repositories. Follow instructions precisely and return only
valid JSON with no extra text."""

# Expanded artifact list for security questions. Existing options retained;
# security-specific options added.
ARTIFACT_OPTIONS = [
    # General project artifacts
    "code",
    "commit_history",
    "issue_tracker",
    "pr_data",
    "ci_logs",
    "contributor_data",
    "documentation",
    "external_reference",
    # Security-specific artifacts
    "advisory",              # GHSA / project advisory write-up
    "cve_cwe_db",            # NVD / MITRE / OSV vulnerability database entry
    "dependency_manifest",   # requirements.txt / package.json / lockfile / SBOM
    "security_scan_logs",    # CodeQL / dependabot / trivy / bandit / semgrep output
    "prior_incident",        # linked past advisory or related security issue
    "none",
    "other",
]


# ── Stage 0: Sanity pre-filter (NO security keywords) ────────────────────────


def prefilter(thread) -> bool:
    """Drop threads that cannot contain any valid Q&A. Not security-specific —
    just a sanity check for substantive non-bot participation. The LLM decides
    whether the content is security-relevant."""
    comments = thread.get("comments", [])

    non_bot = [
        c for c in comments
        if not any(sig in (c.get("author") or "") for sig in ("[bot]", "-bot"))
        and len((c.get("body") or "").strip()) > 20
    ]
    return len(non_bot) >= 2


# ── Stage 1: Security detection ──────────────────────────────────────────────


def build_detection_prompt(thread_text):
    return f"""Read this GitHub thread and decide whether it contains a developer information need related to SECURITY in this project, AND whether the thread contains a concrete answer to that need.

Two independent tests must both pass for INCLUDE = true. Apply them with different stances:

  TEST A — Is the question SECURITY/VULNERABILITY-related?  → BE LENIENT.
  TEST B — Is the answer CONCRETE?            → BE STRICT.

If A is uncertain → favour inclusion (a human will review borderline security tags). If B is uncertain → favour exclusion (we cannot grade an unanchored answer). Both must hold; do not trade one for the other.

<thread>
{thread_text[:50000]}
</thread>

TEST A — Security relevance (LENIENT). Mark security-related if ANY of the following are plausibly true:
- The thread discusses a vulnerability, advisory, CVE, GHSA, CWE, exploit, weakness, or security risk that may affect this project, its dependencies, or its users.
- The thread discusses whether a fix, patch, mitigation, or workaround addresses a security concern in this project — even partially.
- The thread discusses sensitive-data handling (tokens, secrets, credentials, PII, keys), redaction, logging, sanitization, or leakage in this project.
- The thread discusses auth, authz, sessions, cookies, CSRF, XSS, SSRF, RCE, injection (SQL/command/template), deserialization, path traversal, ReDoS, TOCTOU, or similar security-relevant behaviour in this project's code.
- The thread discusses dependency vulnerabilities, transitive risk, supply-chain concerns, SBOM, or scanner findings (CodeQL, dependabot, trivy, semgrep, bandit, etc.) for this project.
- The thread discusses security-relevant configuration, defaults, deprecations, or backward-compatibility tradeoffs.
- The thread discusses the disclosure, triage, embargo, or coordinated-release process for a possible vulnerability in this project.
- The thread otherwise raises a question about this project's security posture and receives an informational response with a concrete anchor (a commit, PR, version, advisory, or citable source).

TEST B — Concrete answer (STRICT). The answer must rest on at least one of:
  (i)  an external IDENTIFIER — a CVE/GHSA/CWE/OSV ID, a fixed-version string, a commit SHA, a PR reference, or an advisory URL; OR
  (ii) a citable SOURCE — project docs, an RFC, a named scanner rule, a linked prior incident thread, or a policy doc that the maintainer explicitly references.

A short answer is fine if it carries an anchor (e.g., "fixed in 2.6.3, see GHSA-XXX" is HIGH-quality concrete, update this code). A long answer without an anchor is NOT concrete.

EXCLUDE as not concrete:
- Pure opinion or judgment without a source: "we don't consider this exploitable" with no further detail, "this is by design" with no doc/RFC reference.
- Deflections: "wrong forum", "ask in discord", "ask support", "this is browser behaviour".
- Unanchored speculation: "probably fine," "should be safe."

Other categorical EXCLUDES (regardless of security-tag confidence — these are confirmed FP patterns):

- The thread has NO response at all (only the original post, no substantive comments), or only automated-bot replies.
- The thread is purely a generic security tutorial unrelated to this project (e.g. asking the maintainers to explain XSS in general).
- **Key/cert FILE-FORMAT usage errors.** The OP cannot load a PEM/DER/JWK because the file is malformed, the wrong type, or in the wrong format, and the answer just explains the correct format. Security-named API surface (PEM, RS256, x5c, JWK) is touched, but no security risk is being assessed. Example BAD include: "PEM_read_bio_ex: bad base64 decode" — answer is "your key file is wrong, use this format."
- **Browser-storage / cookie deflections.** OP reports a cookie isn't saved by Safari / Chrome / iOS, and the answer is "this is browser behaviour, not our library." No security property of this project is being interrogated. Example BAD include: "JWT cookie not stored in Safari due to cross-site tracking prevention" — answer is "wrong forum, can't change browser behaviour."
- **Adapter / config questions that touch a security-named API but ask no security question.** The OP wants to know which adapter to use, why a flag like `rejectUnauthorized` isn't honoured in a test environment, why percent-encoding is preserved on a URL parser. The answer explains the configuration, not a security risk. Example BAD include: jsdom not using the http adapter so the user's `rejectUnauthorized: false` isn't applied — answer is "switch adapter."
- **"Wrong forum" / "ask Stripe support" / "ask in Discord" deflections.** Maintainer's only informational content is "this isn't a question for this repo." No security information about this project is exchanged.
- **Pure regression bugs whose only security-flavoured connection is the file/function/class name** (e.g. a method called `signSafely` crashes, an `auth` route returns 500). If the question is "why does this not work" rather than "is there a security risk here," EXCLUDE.
- **Generic auth misconfig.** OP added authentication to the wrong router, can't reach a public endpoint, etc. — answer is "read the auth docs."

If you are uncertain about TEST A (security-relatedness), INCLUDE — a human will review borderline security tags. If you are uncertain about TEST B (concreteness), EXCLUDE — unanchored answers cannot be graded.

If you include, write ONE SENTENCE summarizing what security information the developer needed to know AND which anchor (identifier or source) the answer rests on. Plain English, no taxonomy labels.

Good summaries:
- "Whether CVE-2023-32681 is exploitable when the application disables redirect following."
- "Which commit in the urllib3 dependency upgrade closed the SSRF window the advisory describes."
- "Whether the new error message redaction logic still leaks the Authorization header under chunked encoding."
- "Whether the missing same-site cookie default is intentional and what the documented threat model assumes."

Return only this JSON:
{{"contains_qa": true or false, "need_summary": "one sentence or empty string", "confidence": "HIGH" or "MEDIUM" or "LOW"}}

Confidence is for downstream sorting during manual review, NOT for filtering. (All confidence levels still require a concrete anchor — TEST B is a hard gate, not a confidence slider.)
- HIGH = clearly security-relevant AND the anchor is unambiguous.
- MEDIUM = security-relevant; the anchor exists but is partial or indirect (e.g. fix version cited but no CVE).
- LOW = security relevance is borderline; the anchor exists and is concrete — included for manual security-tag review."""


# ── Stage 1.5: Hard-fact candidate extraction (regex pre-pass) ──────────────


# Patterns for identifiers we want to surface as candidates for the LLM to
# role-assign. The LLM decides whether each candidate is the cve_subject,
# a fixed_version, an affected_versions range, a fix_pr / fix_commit, an
# advisory_url, or unrelated. We do NOT assign roles here.
_RE_CVE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.I)
_RE_GHSA = re.compile(r"\bGHSA(?:-[a-z0-9]{4}){3}\b", re.I)
_RE_CWE = re.compile(r"\bCWE-\d{1,5}\b", re.I)
_RE_OSV = re.compile(r"\b(?:OSV|PYSEC|GO|RUSTSEC)-\d{4}-\d{2,7}\b", re.I)
_RE_ADVISORY_URL = re.compile(
    r"https?://(?:github\.com/[^\s)]+/security/advisories/[A-Za-z0-9_-]+"
    r"|nvd\.nist\.gov/vuln/detail/[A-Za-z0-9_-]+"
    r"|osv\.dev/vulnerability/[A-Za-z0-9_-]+"
    r"|cve\.mitre\.org/[^\s)]+)",
    re.I,
)
# version token — captured with surrounding context so the LLM can assign role
_RE_VERSION = re.compile(
    r"(?<![\w.])v?\d+\.\d+(?:\.\d+)?(?:[.-][A-Za-z0-9]+)?(?![\w.])"
)
# PR / issue cross-reference like "#1234" — only 3-6 digits to avoid noise
_RE_PR = re.compile(r"(?<![A-Za-z0-9])#\d{2,6}(?![A-Za-z0-9])")
# git short / long SHA — must be at a word boundary
_RE_SHA = re.compile(r"\b[0-9a-f]{7,40}\b", re.I)


def extract_hard_fact_candidates(thread):
    """Run regex pre-pass across the whole thread. Returns a list of candidate
    dicts: {token, kind, comment, surrounding}. The LLM later decides each
    candidate's semantic role and drops the unrelated ones."""
    candidates = []
    seen = set()
    for c in thread.get("comments", []) or []:
        cid = c.get("id", "?")
        body = c.get("body") or ""
        # Skip enormous code-fence-only comments to limit noise
        for kind, pat in (
            ("cve", _RE_CVE),
            ("ghsa", _RE_GHSA),
            ("cwe", _RE_CWE),
            ("osv", _RE_OSV),
            ("advisory_url", _RE_ADVISORY_URL),
            ("version", _RE_VERSION),
            ("pr_ref", _RE_PR),
            ("sha", _RE_SHA),
        ):
            for m in pat.finditer(body):
                tok = m.group(0)
                # SHAs: skip pure-numeric matches that are actually decimals
                if kind == "sha" and tok.isdigit():
                    continue
                # Versions: skip clearly noisy tokens like "3.12" inside long numeric strings
                key = (kind, tok.lower(), cid)
                if key in seen:
                    continue
                seen.add(key)
                start, end = m.span()
                # 60-char context window each side, single line
                ctx_start = max(0, start - 60)
                ctx_end = min(len(body), end + 60)
                surrounding = body[ctx_start:ctx_end].replace("\n", " ").strip()
                candidates.append({
                    "token": tok,
                    "kind": kind,
                    "comment": cid,
                    "surrounding": surrounding,
                })
    # Cap to keep prompt size manageable
    return candidates[:60]


def format_candidates_for_prompt(candidates):
    if not candidates:
        return "(none detected by regex pre-pass — search the thread yourself)"
    lines = []
    for c in candidates:
        lines.append(
            f"- [{c['comment']}] kind={c['kind']:<13} token={c['token']!r:<24} "
            f"ctx={c['surrounding'][:120]!r}"
        )
    return "\n".join(lines)


# ── Stage 2: Security extraction ─────────────────────────────────────────────


def build_extraction_prompt(thread_text, candidates_block):
    artifact_list = ", ".join(f'"{a}"' for a in ARTIFACT_OPTIONS)
    return f"""Read this GitHub thread and extract the core SECURITY question-answer pair.

<thread>
{thread_text[:50000]}
</thread>

Each comment is tagged [c0], [c1], [c2], etc. c0 is the issue or PR body.

A regex pre-pass found these candidate identifiers in the thread (CVE/GHSA/CWE IDs, version numbers, PR/issue refs, SHAs, advisory URLs). Use them when assigning roles in HARD_FACTS below. You may add identifiers the regex missed; you should DROP identifiers that are not actually anchoring the maintainer's answer.

<candidates>
{candidates_block}
</candidates>

Your task:

1. QUESTION TEXT — copy the exact wording of the key security question from the thread. Use the comment ID (cN) to locate it. Prefer the wording that most clearly states the security information need. If c0 is a long bug report or vulnerability disclosure that does not crystallize into a question, and a LATER comment frames the actual question the maintainer answers, use that later comment instead. Do not collapse the question to the issue title.

2. ANSWER TEXT — copy the exact wording of the best answer in the thread. The answer must rest on a concrete anchor: an identifier (CVE/GHSA/CWE/OSV ID, fixed version, commit SHA, PR ref, advisory URL) OR a citable source (project docs, RFC, scanner rule, prior incident thread, policy doc the maintainer references). A short answer is acceptable IF it carries such an anchor (e.g. "fixed in 2.6.3, see GHSA-XXX"). A maintainer's response is preferable to an OP self-answer; if the OP confirms a maintainer-suggested fix, the OP confirmation can be the answer but report answerer_role accordingly. Do NOT extract pure opinion, deflection, or unanchored claims like "we don't consider this exploitable" without further detail — if the thread has no concretely anchored answer, leave answer_text empty and the downstream gate will drop it.

3. ARTIFACTS NEEDED — which project / external artifacts would a tool need to answer this security question? Choose any number from:
   {artifact_list}
   Security-specific options:
   - "advisory" — a GHSA or project security advisory write-up
   - "cve_cwe_db" — an NVD / MITRE / OSV database entry for the CVE/CWE
   - "dependency_manifest" — requirements.txt, package.json, lockfiles, SBOM
   - "security_scan_logs" — CodeQL / dependabot / trivy / bandit / semgrep output
   - "prior_incident" — a linked past advisory or related earlier security issue
   Use "none" ONLY if the answer is purely a definitional or policy statement requiring no external lookup. If the answer cites docs, an RFC, a convention, or a behaviour pattern, prefer "documentation" over "none". If a non-listed artifact is needed, use "other-{{type}}".

4. HARD_FACTS — the externally-checkable identifiers that anchor the answer. Each field is a list (empty if no such fact appears). Be conservative: include only identifiers that are actually load-bearing in the answer or in the question being answered. Do NOT include incidental environment metadata (Python/OpenSSL/Node version numbers in a bug-report environment block).
   - "cve_ids":           CVE IDs that are the SUBJECT of the Q&A (the question is about them, or the answer cites them as the relevant CVE)
   - "ghsa_ids":          GHSA IDs anchoring the answer
   - "cwe_ids":           CWE classifications referenced
   - "osv_ids":           OSV / PYSEC / RUSTSEC / GO style IDs
   - "fixed_versions":    project version(s) in which the issue is FIXED (e.g. "2.6.3", "1.7.4")
   - "affected_versions": project version range(s) that ARE vulnerable (e.g. "1.3.2 - 1.7.3", "0.x")
   - "fix_prs":           PR / issue numbers (write as "#3736") that contain or track the fix
   - "fix_commits":       commit SHAs (7+ hex chars) that introduce the fix
   - "advisory_urls":     full URLs to GHSA / NVD / OSV / vendor advisory pages

5. SECURITY_TOPIC — one short free-text phrase describing what the question is about, for downstream open / axial coding. Do not use a fixed taxonomy.
   Examples: "applicability of CVE to specific configuration", "sufficiency of redaction against token leakage", "regression-localization for known advisory", "transitive-dependency vulnerability impact", "design rationale of CSRF mitigation", "severity assessment for chained exploit".

6. ANSWERER_ROLE:
   - "maintainer" = commit rights or core contributor of THIS project
   - "contributor" = has contributed before but not core
   - "commenter" = community member with no known contribution
   - "op_self"    = answer_author == question_author (the OP answered themselves)
   - "bot"        = automated response

Return only this JSON:
{{
  "question_comment_id": "cN",
  "question_author": "GitHub username or empty string",
  "question_text": "verbatim question text",
  "answer_comment_id": "cN",
  "answer_author": "GitHub username or empty string",
  "answer_text": "verbatim answer text",
  "artifacts_needed": ["..."],
  "hard_facts": {{
    "cve_ids": [], "ghsa_ids": [], "cwe_ids": [], "osv_ids": [],
    "fixed_versions": [], "affected_versions": [],
    "fix_prs": [], "fix_commits": [], "advisory_urls": []
  }},
  "security_topic": "short free-text phrase",
  "answerer_role": "maintainer or contributor or commenter or op_self or bot",
  "confidence": "HIGH or MEDIUM or LOW"
}}"""


# ── Core detection function ──────────────────────────────────────────────────


_CONF = {"HIGH": 0.95, "MEDIUM": 0.75, "LOW": 0.5}

# Conditional answer-length floor: drop unconditionally below MIN_ANSWER_CHARS;
# between MIN and SOFT_FLOOR, accept only if at least one hard_fact is populated
# (a 40-char "fixed in 2.6.3, see GHSA-XXX" carries more research signal than a
# 200-char "wrong forum, ask discord" deflection).
MIN_ANSWER_CHARS = 30
SOFT_FLOOR_CHARS = 100

# Self-Consistency on Stage 1: sample N times, majority-vote `contains_qa`,
# take the highest-frequency confidence and the longest non-empty need_summary
# from the contains_qa=True votes. N=1 disables self-consistency.
STAGE1_SAMPLES = 3


def _hard_facts_empty():
    return {
        "cve_ids": [], "ghsa_ids": [], "cwe_ids": [], "osv_ids": [],
        "fixed_versions": [], "affected_versions": [],
        "fix_prs": [], "fix_commits": [], "advisory_urls": [],
    }


def _normalize_hard_facts(raw):
    """Coerce the LLM's hard_facts dict to the canonical shape, even if it
    omitted keys or returned strings instead of lists."""
    out = _hard_facts_empty()
    if not isinstance(raw, dict):
        return out
    for k in out:
        v = raw.get(k, [])
        if v is None:
            continue
        if not isinstance(v, list):
            v = [v]
        out[k] = [str(x).strip() for x in v if str(x).strip()]
    return out


def _hard_facts_has_any(hf):
    return any(len(v) > 0 for v in hf.values())


def _flatten_references(hf):
    """Backward-compat: emit a flat references list (the v1 schema field)
    containing CVE/GHSA/CWE/OSV IDs and advisory URLs. Hard versions/SHAs/PRs
    are excluded — they belong to hard_facts only."""
    refs = []
    refs += hf.get("cve_ids", [])
    refs += hf.get("ghsa_ids", [])
    refs += hf.get("cwe_ids", [])
    refs += hf.get("osv_ids", [])
    refs += hf.get("advisory_urls", [])
    # de-dupe while preserving order
    seen = set()
    out = []
    for r in refs:
        ru = r.upper()
        if ru in seen:
            continue
        seen.add(ru)
        out.append(r)
    return out


def _stage1_self_consistent(thread_text, model, n_samples=None):
    """Run Stage 1 N times, majority-vote contains_qa. Returns the winning
    decision and the merged confidence/summary. With N=1 this is identical
    to a single call. n_samples=None resolves to the module-level
    STAGE1_SAMPLES at call time so CLI overrides take effect."""
    if n_samples is None:
        n_samples = STAGE1_SAMPLES
    votes = []
    for _ in range(max(1, n_samples)):
        out = generate_json(
            build_detection_prompt(thread_text),
            model=model,
            system=SYSTEM_PROMPT,
            max_tokens=512,
        )
        if out:
            votes.append(out)

    if not votes:
        return None

    yes = [v for v in votes if v.get("contains_qa")]
    no = [v for v in votes if not v.get("contains_qa")]
    contains_qa = len(yes) > len(no)  # strict majority; ties fall to "no"
    pool = yes if contains_qa else no
    # majority confidence label within the winning pool
    confs = [str(v.get("confidence", "LOW")).upper() for v in pool]
    conf_label = max(set(confs), key=confs.count) if confs else "LOW"
    # longest non-empty need_summary from the winning pool
    summaries = sorted(
        (v.get("need_summary", "").strip() for v in pool),
        key=len, reverse=True,
    )
    need_summary = next((s for s in summaries if s), "")
    return {
        "contains_qa": contains_qa,
        "confidence": conf_label,
        "need_summary": need_summary,
        "n_samples": len(votes),
        "n_yes": len(yes),
    }


def detect_and_extract(thread, model):
    """Run Stage 1 + Stage 2. Returns result dict or None on parse failure."""
    thread_text = thread["thread_text"]
    comment_lookup = {c["id"]: c.get("body", "") for c in thread.get("comments", [])}

    # Stage 1 — security detection (self-consistent across N samples)
    s1 = _stage1_self_consistent(thread_text, model)
    print(f"  [s1] {s1}")

    if not s1:
        return {"contains_qa": False, "drop_reason": "s1_no_response"}
    if not s1.get("contains_qa"):
        return {"contains_qa": False, "drop_reason": "s1_not_security"}

    s1_conf = _CONF.get(s1.get("confidence", "LOW"), 0.5)
    need_summary = s1.get("need_summary", "")

    # Stage 1.5 — regex pre-pass for hard-fact candidates
    candidates = extract_hard_fact_candidates(thread)
    candidates_block = format_candidates_for_prompt(candidates)

    # Stage 2 — security extraction (with candidates injected)
    s2 = generate_json(
        build_extraction_prompt(thread_text, candidates_block),
        model=model,
        system=SYSTEM_PROMPT,
        max_tokens=2048,  # raised: hard_facts schema is wider than v1 references
    )
    print(f"  [s2] {s2}")

    if not s2:
        return None

    q_comment_id = s2.get("question_comment_id", "c0")
    a_comment_id = s2.get("answer_comment_id", "")

    if q_comment_id not in comment_lookup and q_comment_id != "c0":
        q_comment_id = "c0"
    if a_comment_id and a_comment_id not in comment_lookup:
        print(f"  [warn] answer_comment_id {a_comment_id!r} not in lookup — clearing")
        a_comment_id = ""

    q_text = s2.get("question_text") or comment_lookup.get(q_comment_id, "")
    a_text = s2.get("answer_text") or comment_lookup.get(a_comment_id, "")
    a_len = len(a_text.strip())

    # Normalize hard_facts and artifacts; emit a flat references list for compat
    hard_facts = _normalize_hard_facts(s2.get("hard_facts"))
    has_hard = _hard_facts_has_any(hard_facts)

    artifacts = s2.get("artifacts_needed", [])
    if not isinstance(artifacts, list):
        artifacts = [artifacts] if artifacts else []
    has_source = bool(artifacts) and artifacts != ["none"]

    # Length floor: drop anything below the hard minimum.
    if a_len < MIN_ANSWER_CHARS:
        print(f"  [drop] answer too short ({a_len} chars, hard min {MIN_ANSWER_CHARS})")
        return {"contains_qa": False, "drop_reason": "answer_too_short"}

    # Anchor gate: every accepted pair must be verifiable in principle —
    # either through an identifier in hard_facts (deterministic grading) or
    # through a citable source in artifacts_needed (source-anchored grading).
    # Pure opinion / deflection without an anchor is dropped.
    if not has_hard and not has_source:
        print(f"  [drop] no anchor (no hard_facts, artifacts_needed empty/none)")
        return {"contains_qa": False, "drop_reason": "no_anchor"}

    # Thin-answer guard: between MIN and SOFT_FLOOR we additionally require
    # an identifier anchor (a 40-char "fixed in 2.6.3, see GHSA-XXX" is in;
    # a 40-char "see our docs" is out — the source claim needs more substance).
    if a_len < SOFT_FLOOR_CHARS and not has_hard:
        print(f"  [drop] thin answer ({a_len} chars) and no hard_facts")
        return {"contains_qa": False, "drop_reason": "thin_source_only"}

    s2_conf = _CONF.get(str(s2.get("confidence", "LOW")).upper(), 0.5)

    # Derive answerer_role override: op_self when authors match
    q_author = s2.get("question_author", "") or ""
    a_author = s2.get("answer_author", "") or ""
    role = s2.get("answerer_role", "commenter") or "commenter"
    if q_author and a_author and q_author == a_author and role not in ("op_self",):
        role = "op_self"

    return {
        "contains_qa": True,
        "need_summary": need_summary,
        "question_comment_id": q_comment_id,
        "question_author": q_author,
        "question_text": q_text,
        "answer_comment_id": a_comment_id,
        "answer_author": a_author,
        "answer_text": a_text,
        "artifacts_needed": artifacts,
        "hard_facts": hard_facts,
        "references": _flatten_references(hard_facts),  # backward-compat flat list
        "security_topic": s2.get("security_topic", "").strip(),
        "answerer_role": role,
        "stage1_confidence": s1.get("confidence", "LOW"),
        "stage1_n_yes": s1.get("n_yes", 0),
        "stage1_n_samples": s1.get("n_samples", 1),
        "stage2_confidence": str(s2.get("confidence", "LOW")).upper(),
        "confidence": s1_conf * s2_conf,
    }


# ── Main runner ──────────────────────────────────────────────────────────────


def run(repo, model=STAGE1_MODEL, confidence_threshold=0.3, limit=None,
        max_pairs=None, force=False, state_filter=None):
    if not is_running():
        print("  [error] Ollama not running — start with: ollama serve")
        return

    print(f"\n[detect_security_qa] {repo}")
    print(f"  model:      {model}")
    print(f"  threshold:  {confidence_threshold}")
    print(f"  S1 samples: {STAGE1_SAMPLES} (self-consistency)")
    print(f"  ans floor:  hard>={MIN_ANSWER_CHARS}  soft>={SOFT_FLOOR_CHARS} (or hard_facts)")
    if state_filter:
        print(f"  state:      {state_filter}")
    if max_pairs:
        print(f"  cap/repo:   {max_pairs}")

    if max_pairs and not force:
        existing = load_jsonl(repo, "security_qa_pairs")
        if existing and len(existing) >= max_pairs:
            print(f"  [skip] already have {len(existing)} pairs >= max_pairs={max_pairs}")
            return

    threads = load_jsonl(repo, "raw_threads")
    if not threads:
        print("  [error] no raw_threads.jsonl — run mine_threads.py first")
        return

    checkpoint_key = f"detect_security_qa_{model}".replace(":", "_").replace("/", "_")
    done = set() if force else load_checkpoint(repo, checkpoint_key)

    threads_to_do = [t for t in threads if t["number"] not in done]
    if state_filter:
        threads_to_do = [t for t in threads_to_do if t.get("state", "").lower() == state_filter]
    threads_to_do.sort(key=lambda t: t["number"], reverse=True)
    if limit:
        threads_to_do = threads_to_do[:limit]

    print(f"  threads total:   {len(threads)}")
    print(f"  already done:    {len(done)}")
    print(f"  to process:      {len(threads_to_do)}")
    if max_pairs:
        print(f"  max pairs:       {max_pairs}")

    if force:
        out_path = f"output/{repo.replace('/','__')}/security_qa_pairs.jsonl"
        if os.path.exists(out_path):
            os.remove(out_path)
            print("  cleared previous output")

    existing_count = 0 if force else len(load_jsonl(repo, "security_qa_pairs") or [])
    accepted = existing_count
    dropped_prefilter = dropped_conf = failed = 0
    dropped_by_reason: dict = {}

    for thread in tqdm(threads_to_do, desc="  detecting"):
        done.add(thread["number"])

        if not prefilter(thread):
            dropped_prefilter += 1
            continue

        result = detect_and_extract(thread, model)

        if result is None:
            failed += 1
            continue

        if not result.get("contains_qa"):
            reason = result.get("drop_reason", "unknown")
            dropped_by_reason[reason] = dropped_by_reason.get(reason, 0) + 1
            continue

        if result.get("confidence", 0) < confidence_threshold:
            print(f"  [drop] confidence {result.get('confidence', 0):.2f} < {confidence_threshold}")
            dropped_conf += 1
            continue

        record = {
            "source": thread["source"],
            "repo": repo,
            "number": thread["number"],
            "title": thread.get("title", ""),
            "url": thread.get("url", ""),
            "state": thread.get("state", ""),
            "created_at": thread.get("created_at", ""),
            "question_id": "SECURITY_OPEN",
            "need_summary": result["need_summary"],
            "security_topic": result["security_topic"],
            "question_comment_id": result["question_comment_id"],
            "question_author": result["question_author"],
            "question_text": result["question_text"],
            "answer_comment_id": result["answer_comment_id"],
            "answer_author": result["answer_author"],
            "answer_text": result["answer_text"],
            "artifacts_needed": result["artifacts_needed"],
            "hard_facts": result["hard_facts"],
            "references": result["references"],  # backward-compat flat list
            "answerer_role": result["answerer_role"],
            "stage1_confidence": result["stage1_confidence"],
            "stage1_n_yes": result["stage1_n_yes"],
            "stage1_n_samples": result["stage1_n_samples"],
            "stage2_confidence": result["stage2_confidence"],
            "confidence": result["confidence"],
            "thread_text": thread["thread_text"],
            "comments": thread.get("comments", []),
            "model": model,
        }

        accepted += 1
        append_record(repo, "security_qa_pairs", record)

        if max_pairs and accepted >= max_pairs:
            done.add(thread["number"])
            print(f"  [stop] reached max_pairs={max_pairs}")
            break

        if len(done) % 10 == 0:
            save_checkpoint(repo, checkpoint_key, done)

    save_checkpoint(repo, checkpoint_key, done)

    new_accepted = accepted - existing_count
    total_dropped = sum(dropped_by_reason.values())
    print("\n  results:")
    print(f"    accepted (this run): {new_accepted}  (total: {accepted})")
    print(f"    pre-filter drop:     {dropped_prefilter}")
    print(f"    detect/extract drop: {total_dropped}")
    for reason in sorted(dropped_by_reason):
        print(f"      - {reason:20s} {dropped_by_reason[reason]}")
    print(f"    low confidence:      {dropped_conf}")
    print(f"    parse failures:      {failed}")
    denom = max(1, len(threads_to_do) - dropped_prefilter)
    yield_pct = int(100 * new_accepted / denom)
    print(f"    yield (post-filter): {yield_pct}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=None)
    parser.add_argument("--model", default=STAGE1_MODEL)
    parser.add_argument("--confidence", type=float, default=0.3,
                        help="Min confidence threshold (0–1, default 0.3 — recall-favoring; manual review filters false positives later)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Cap threads to process (for testing)")
    parser.add_argument("--max-pairs", type=int, default=None,
                        help="Stop after extracting N valid security pairs")
    parser.add_argument("--force", action="store_true",
                        help="Re-process all threads from scratch")
    parser.add_argument("--state", choices=["open", "closed"], default=None,
                        help="Filter threads by issue state (default: all)")
    parser.add_argument("--stage1-samples", type=int, default=None,
                        help=f"Stage-1 self-consistency sample count (default {STAGE1_SAMPLES}; set 1 to disable)")
    args = parser.parse_args()

    if args.stage1_samples is not None:
        # Rebind the module-level name so _stage1_self_consistent picks it up
        # at call time (its n_samples default is None).
        globals()["STAGE1_SAMPLES"] = args.stage1_samples

    repos = [args.repo] if args.repo else REPOS
    for repo in repos:
        run(
            repo,
            model=args.model,
            confidence_threshold=args.confidence,
            limit=args.limit,
            max_pairs=args.max_pairs,
            force=args.force,
            state_filter=args.state,
        )
