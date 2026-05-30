"""
Security-focused Q&A detection pipeline (Track B — security scope, Stage 1+2).

Mines real developer SECURITY information needs from public OSS threads.
No keyword pre-filter — the LLM decides what counts as security. The only
pre-filter is the sanity check that the thread has substantive non-bot
participation.

Stage 1: Detect whether thread contains a valid security-related developer
         information need. Emits free-text need_summary — no fixed enum, for
         later open + axial coding into the security taxonomy.
Stage 2: Extract verbatim Q, verbatim A, artifacts needed (including
         security-specific artifact types), references (CVE/GHSA/CWE IDs and
         advisory URLs mentioned in the answer), a free-text security_topic
         phrase.

Output: output/<owner>__<repo>/security_qa_pairs.jsonl

Usage:
  python detect_security_qa.py --repo psf/requests
  python detect_security_qa.py --repo psf/requests --limit 500
  python detect_security_qa.py --repo psf/requests --max-pairs 50 --force
"""

import argparse
import os
import random
import sys

from tqdm import tqdm

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.ollama_client import STAGE1_MODEL, generate_json, is_running
from utils.storage import (append_record, load_checkpoint, load_jsonl,
                           save_checkpoint)

random.seed(777)

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
    comments = thread.get("comments", [])

    non_bot = [
        c for c in comments
        if len((c.get("body") or "").strip()) > 20
    ]
    return len(non_bot) >= 2


# ── Stage 1: Security detection ──────────────────────────────────────────────


def build_detection_prompt(thread_text):
    return f"""Read this GitHub thread and decide whether it PLAUSIBLY contains a developer information need related to SECURITY in this project. We strongly favour RECALL over precision — borderline cases will be manually reviewed afterwards, so when in doubt, INCLUDE the thread. Missed pairs are lost; false positives are cheap.

<thread>
{thread_text[:50000]}
</thread>

The core test: does the thread contain a QUESTION (explicit or implicit) about a security property, risk, or vulnerability of THIS project, and does AT LEAST ONE comment provide some informational response — even partial, even a one-line pointer to a commit, PR, version, or advisory?

INCLUDE the thread if ANY of the following are plausibly true:
- Someone asks whether a CVE, GHSA, CWE, exploit, advisory, or known weakness affects this project, its dependencies, or its users — and someone responds.
- Someone asks whether a fix, patch, mitigation, or workaround addresses a security concern in this project — and someone responds.
- Someone raises a concern about sensitive-data handling (tokens, secrets, credentials, PII, keys), redaction, logging, sanitization, or leakage in this project's code or defaults — and someone responds.
- Someone questions auth, authz, sessions, cookies, CSRF, XSS, SSRF, RCE, injection, deserialization, path traversal, ReDoS, TOCTOU, or similar security-relevant behavior in THIS project — and someone responds.
- Someone asks about dependency vulnerabilities, transitive risk, supply-chain concerns, or scanner findings (CodeQL, dependabot, trivy, semgrep, bandit, etc.) against this project — and someone responds.
- Someone asks about security-relevant configuration, file/data permissions, defaults, or backward-compatibility tradeoffs with a security implication — and someone responds.
- Someone discloses or triages a possible vulnerability in this project and receives any substantive response.

EXCLUDE the following cases:
- The thread has NO substantive response — only the original post, or only bot/automated replies.
- The thread is a pure regression bug or crash report where security words appear only incidentally (e.g. a path containing "token", a method named "private", a type called "Permission") but no one is asking about a security risk.
- The thread is a pure type error, compiler error, or API usage question — even if it touches something security-named — where the actual question is "why does this code not compile / run" rather than "is there a security risk here."
- The thread is a feature request for new security capability (add 2FA, support OAuth, etc.) with no question about the CURRENT security behavior or posture of the project.
- The thread is a routine dependency version bump where no one discusses vulnerability impact or affected users.
- The thread is purely a general "how do I use this library" usage question with no security risk angle (e.g. "how do I set a header correctly").
- The thread is a generic security tutorial unrelated to this project.
- Security-adjacent words ("secure", "safe", "trusted", "private") appear only in passing with no actual security concern raised.

If you are uncertain whether the thread is security-related, or whether the answer is "substantive enough," INCLUDE it. A human will review and filter false positives.

If you include, write ONE SENTENCE summarizing what security information the developer needed to know, grounded in THIS project's specific behavior or codebase.

Good summaries:
- "Whether CVE-2023-32681 is exploitable when the application disables redirect following."
- "Which commit in the urllib3 dependency upgrade closed the SSRF window the advisory describes."
- "Whether the new error message redaction logic still leaks the Authorization header under chunked encoding."
- "Whether the default 600 permissions on ruff cache files are an intentional security decision or an unintended restriction."
- "Whether hardcoding the JWT salt in source code creates a real exploitable risk and how to fix it."

BAD summaries (these are FPs — do not include):
- "Developer asks why backslashes appear in RECORD file paths" — pure regression bug, no security risk.
- "Developer wants to know how to suppress a React warning about document.body" — pure usage question.
- "Developer asks where to enforce RBAC in their system" — architecture preference, not a security risk in THIS project.
- "Developer gets a type error calling generateTestHeaderString" — type/API usage error, not a security concern.

Return only this JSON:
{{"contains_qa": true or false, "need_summary": "one sentence or empty string", "confidence": "HIGH" or "MEDIUM" or "LOW"}}

Confidence is for downstream sorting during manual review, NOT for filtering:
- HIGH = clearly security-relevant AND the answer is substantive.
- MEDIUM = security-relevant but the answer is partial, brief, or indirect.
- LOW = tangentially security-related OR the answer is short / weakly informative — still include it."""


# ── Stage 2: Security extraction ─────────────────────────────────────────────


def build_extraction_prompt(thread_text):
    artifact_list = ", ".join(f'"{a}"' for a in ARTIFACT_OPTIONS)
    return f"""Read this GitHub thread and extract the core SECURITY question-answer pair.

<thread>
{thread_text[:50000]}
</thread>

Each comment is tagged [c0], [c1], [c2], etc. c0 is the issue or PR body.

Your task:

1. QUESTION TEXT — copy the exact wording of the key security question from the thread. Use the comment ID (cN) to locate it. The question is the sentence or paragraph that most clearly states the security information need.

2. ANSWER TEXT — copy the exact wording of the best answer in the thread. Aim for substantive content (a full sentence with real information), but if the answer is short while still carrying real informational signal — a pointer to a commit/PR/version, a yes/no with a brief reason, a status statement, a non-exploitability claim — STILL extract it. Only treat the thread as having no answer if there is genuinely nothing informational anywhere in the comments.

3. ARTIFACTS NEEDED — which project / external artifacts would a tool need to answer this security question? Choose any number from:
   {artifact_list}
   Use security-specific options where applicable:
   - "advisory" — a GHSA or project security advisory write-up
   - "cve_cwe_db" — an NVD / MITRE / OSV database entry for the CVE/CWE
   - "dependency_manifest" — requirements.txt, package.json, lockfiles, SBOM
   - "security_scan_logs" — CodeQL / dependabot / trivy / bandit / semgrep output
   - "prior_incident" — a linked past advisory or related earlier security issue
   If a non-listed artifact is needed, use "other-{{type}}". If the answer is fully self-contained in the thread, use "none".

4. REFERENCES — list every CVE ID, GHSA ID, CWE ID, OSV ID, or advisory URL that appears in the ANSWER. Examples: "CVE-2023-32681", "GHSA-j8r2-6x86-q33q", "CWE-79", "https://github.com/.../security/advisories/GHSA-...". Empty list if none.

5. SECURITY_TOPIC — one short free-text phrase describing what the question is about, for downstream open / axial coding. Do not use a fixed taxonomy. Examples:
   - "applicability of CVE to specific configuration"
   - "sufficiency of redaction against token leakage"
   - "regression-localization for known advisory"
   - "transitive-dependency vulnerability impact"
   - "design rationale of CSRF mitigation"
   - "severity assessment for chained exploit"

Return only this JSON:
{{
  "question_comment_id": "cN tag where the question appears, e.g. c0",
  "question_author": "GitHub username or empty string",
  "question_text": "verbatim question text from the thread",
  "answer_comment_id": "cN tag where the best answer appears",
  "answer_author": "GitHub username or empty string",
  "answer_text": "verbatim answer text from the thread",
  "artifacts_needed": ["list", "of", "artifact", "types"],
  "references": ["CVE-...", "GHSA-...", "https://..."],
  "security_topic": "short free-text phrase",
  "confidence": "HIGH or MEDIUM or LOW"
}}"""


# ── Core detection function ──────────────────────────────────────────────────


_CONF = {"HIGH": 0.95, "MEDIUM": 0.75, "LOW": 0.5}


def detect_and_extract(thread, model):
    """Run Stage 1 + Stage 2. Returns result dict or None on parse failure."""
    thread_text = thread["thread_text"]
    comment_lookup = {c["id"]: c.get("body", "") for c in thread.get("comments", [])}

    # Stage 1 — security detection
    s1 = generate_json(
        build_detection_prompt(thread_text),
        model=model,
        system=SYSTEM_PROMPT,
        max_tokens=300,
    )
    print(f"  [s1] {s1}")

    if not s1 or not s1.get("contains_qa"):
        return {"contains_qa": False}

    s1_conf = _CONF.get(str(s1.get("confidence", "LOW")).upper(), 0.5)
    need_summary = s1.get("need_summary", "").strip()

    # Stage 2 — security extraction
    s2 = generate_json(
        build_extraction_prompt(thread_text),
        model=model,
        system=SYSTEM_PROMPT,
        max_tokens=800,
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

    if len(a_text.strip()) < 30:
        print(f"  [drop] answer too short ({len(a_text.strip())} chars)")
        return {"contains_qa": False}

    s2_conf = _CONF.get(str(s2.get("confidence", "LOW")).upper(), 0.5)

    # Normalize references and artifacts to lists
    refs = s2.get("references", [])
    if not isinstance(refs, list):
        refs = [refs] if refs else []
    artifacts = s2.get("artifacts_needed", [])
    if not isinstance(artifacts, list):
        artifacts = [artifacts] if artifacts else []

    return {
        "contains_qa": True,
        "need_summary": need_summary,
        "question_comment_id": q_comment_id,
        "question_author": s2.get("question_author", ""),
        "question_text": q_text,
        "answer_comment_id": a_comment_id,
        "answer_author": s2.get("answer_author", ""),
        "answer_text": a_text,
        "artifacts_needed": artifacts,
        "references": refs,
        "security_topic": s2.get("security_topic", "").strip(),
        "stage1_confidence": str(s1.get("confidence", "LOW")).upper(),
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
    if state_filter:
        print(f"  state:      {state_filter}")

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
    dropped_prefilter = dropped_no_qa = dropped_conf = failed = 0

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
            dropped_no_qa += 1
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
            "references": result["references"],
            "stage1_confidence": result["stage1_confidence"],
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

        if len(done) % 50 == 0:
            save_checkpoint(repo, checkpoint_key, done)

    save_checkpoint(repo, checkpoint_key, done)

    new_accepted = accepted - existing_count
    print("\n  results:")
    print(f"    accepted (this run): {new_accepted}  (total: {accepted})")
    print(f"    pre-filter drop:     {dropped_prefilter}")
    print(f"    no security Q&A:     {dropped_no_qa}")
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
    args = parser.parse_args()

    if args.repo:
        repos = [args.repo]
    else:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "output")
        repos = sorted(
            os.path.basename(d).replace("__", "/", 1)
            for d in os.scandir(output_dir)
            if d.is_dir() and os.path.exists(os.path.join(d.path, "raw_threads.jsonl"))
        )
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