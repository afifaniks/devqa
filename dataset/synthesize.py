"""
SecDevQA — Stage 1: synthesize gradeable QA pairs from GitHub security threads.

Objective (deliberately minimal — this is the only stage for now):
  thread  ->  one or more (question, answer) pairs where
    * the QUESTION is the developer's real question made self-contained: it carries
      sufficient context to be answered standalone, and does NOT state the resolution
      (so it stays a real, unanswered question);
    * the ANSWER is grounded EXACTLY on the thread — a faithful, distilled statement of
      how the maintainer actually answered, never invented beyond what the thread says.

Each pair is labelled with a KNOWLEDGE TYPE (the only knowledge distinction we keep):
    * "parametric" — the maintainer answered from general knowledge, citing nothing
      external: an LLM could answer it without the repo or any document.
    * "grounded"   — the answer rests on a repository artifact and/or an external source
      (advisory DB, doc, PR/commit, another issue) that appears in the thread.
  and with `grounding_sources`: the in-thread references the answer relied on
  (attribution, GaRAGe-style). [] for parametric.

Construction policy (per the user's chosen design):
  * Start from the human-curated (question_comment_id -> answer_comment_id) pair.
  * DECOMPOSE that one exchange into multiple QA pairs only when the reporter bundled
    distinct questions AND the maintainer's answer actually addresses more than one.
  * Ground strictly on IN-THREAD text. We do not fetch external advisories / PR diffs
    here; we only record what the thread itself contains/links.

Grounding in established practice: authentic-question preservation (StackRepoQA/
StackEval), per-source answer attribution (GaRAGe, ACL-Findings 2025), and multi-intent
decomposition only when genuinely multi-intent (claim-decomposition line).

Input:  dataset/security_benchmark_filtered.jsonl  (one thread per line)
Output: dataset/eval_pairs.jsonl                   (one thread per line, with qa_pairs[])

Usage:
  python -m dataset.synthesize
  python -m dataset.synthesize --limit 5
  python -m dataset.synthesize --model openai/gpt-5.4-mini --force
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import litellm
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent
DEFAULT_INPUT = ROOT / "dataset" / "security_benchmark_filtered.jsonl"
DEFAULT_OUTPUT = ROOT / "dataset" / "eval_pairs.jsonl"
DEFAULT_MODEL = "openai/gpt-5.5"

# In-thread reference patterns — used to (a) detect whether an answer is grounded and
# (b) flag the fix being leaked into the question.
URL_RE = re.compile(r"https?://[^\s\)\"'<>]+")
ISSUE_REF_RE = re.compile(r"(?<![\w/])#\d+\b")
CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.I)
GHSA_RE = re.compile(r"\bGHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}\b", re.I)
SHA_RE = re.compile(r"\b[0-9a-f]{40}\b", re.I)


# ---------------------------------------------------------------------------
# Thread helpers
# ---------------------------------------------------------------------------

def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Bad JSON at {path}:{lineno}: {exc}") from exc
    return rows


def comment_by_id(thread: dict, cid: str) -> dict | None:
    for c in thread.get("comments", []):
        if c.get("id") == cid:
            return c
    return None


def context_before_answer(thread: dict) -> list[dict]:
    """All comments up to (not including) the answer comment — the context a reader had
    when the question was being asked/clarified."""
    out = []
    for c in thread.get("comments", []):
        if c.get("id") == thread.get("answer_comment_id"):
            break
        out.append(c)
    return out


def detect_refs(text: str) -> list[str]:
    """In-thread references that signal external/repo grounding."""
    refs = set()
    refs |= set(m.rstrip(".,);") for m in URL_RE.findall(text))
    refs |= set(ISSUE_REF_RE.findall(text))
    refs |= set(x.upper() for x in CVE_RE.findall(text))
    refs |= set(x.upper() for x in GHSA_RE.findall(text))
    refs |= set(SHA_RE.findall(text))
    return sorted(refs)


def build_thread_view(thread: dict) -> str:
    """Render the thread for the LLM: title, the reporter/context comments, and the
    maintainer's answer comment clearly marked."""
    parts = [f"# Issue: {thread.get('title','')}", f"Repository: {thread.get('repo','')}", ""]
    answer_id = thread.get("answer_comment_id")
    q_id = thread.get("question_comment_id")
    for c in thread.get("comments", []):
        tag = []
        if c.get("id") == q_id:
            tag.append("REPORTER QUESTION")
        if c.get("id") == answer_id:
            tag.append("MAINTAINER ANSWER")
        label = f" [{' / '.join(tag)}]" if tag else ""
        body = c.get("body", "")
        if len(body) > 20000:
            body = body[:20000] + f"\n... [truncated {len(c['body'])} chars]"
        parts.append(f"--- comment {c.get('id')} by {c.get('author','?')}"
                     f" ({c.get('role','')}){label} ---\n{body}\n")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

# TODO: I think we could slightly simplify the types. Knowledge is when no grounding sources are cited, and grounding is whent at least one 

NORMALIZE_PROMPT = """\
You convert a GitHub security issue thread into one or more gradeable (question, \
answer) pairs for a developer-security benchmark. You are given the full thread with \
the REPORTER QUESTION and the MAINTAINER ANSWER comments marked.

Produce QA pairs that are faithful to what was actually asked and answered.

THE QUESTION (one per developer information-need):
- Reconstruct the developer's real question and make it SELF-CONTAINED: include every \
  concrete specific the reporter gave (versions, environment, exact error/stack trace, \
  configuration, the observed behaviour, any code/PoC — keep code verbatim). Resolve \
  references like "the above" / "this issue" using earlier comments.
- Phrase it as the genuine question a developer would ask. Do NOT state or presuppose \
  the resolution/fix (fixed version, patch PR/commit, advisory id introduced as the \
  answer, verdict). The question may ASK for these; it must not reveal them. A CVE/GHSA \
  or affected version the reporter themselves cites as their SUBJECT may stay.

THE ANSWER (grounded EXACTLY on the thread):
- Concisely state the complete answer to the question how the maintainer/community actually answered — distilled \
  faithfully from the thread. Include any additional artifacts (e.g., code snippets, links) that are used in the answer. \
  Do NOT add fillers, facts, fixes, or reasoning that are not in the \
  thread. If the thread answer is terse or points elsewhere, reflect that honestly \
  (e.g. "It is fixed and points to PR #932", "A fix to this issue is {{code}}").

KNOWLEDGE TYPE (judge from what the answer's correctness actually rests on)
- "parametric": the answer is a security/engineering fact or remediation any expert \
  could give from general knowledge and no repository artifacts are linked (e.g., issue, PR, commit, external advisory, references, etc.)
  , or from a public standard/advisory the QUESTION \
  itself already cites — WITHOUT this project's source, releases, or internals. E.g. \
  "an RSA key must be >= 2048 bits for JOSE", "never trust a JWT with alg=none". \
  Correct, specific general knowledge is still parametric: an LLM could answer it alone.
- "grounded": the answer's correctness rests on THIS project's specifics or an external \
  source the thread points to. This INCLUDES stating that the issue is fixed in a \
  specific release, PR, or commit of this project — even tersely, even as a bare \
  version number (e.g. "fixed in vX.Y.Z") — because an LLM cannot know this project's \
  internal release/PR/commit identifiers without the repository. It also includes a \
  change in this library's behaviour between versions (e.g. a new default), any other \
  non-obvious behaviour of this library, or an advisory/CVE/GHSA record, documentation, \
  or another issue the answer relies on.
For grounded pairs, `grounding_sources` lists the EXTERNAL/REPO things the answer relied \
on (e.g. "PR #932", "fixed version 2.3.1", "https://...advisory", "axios only copies \
the XSRF cookie into a header"). The answer's OWN comment is NEVER a source (do not list \
"comment cN"), and generic support/contact links (Discord, chat, mailing list, "ask the \
community") are NEVER sources. Use [] for parametric.

DECOMPOSITION:
- Emit MULTIPLE pairs ONLY when the reporter raised distinct questions AND the answer \
  addresses more than one of them. Otherwise emit only a single pair. Never invent a \
  question the thread does not answer.

Output ONLY a JSON object — no preamble, no markdown:
{
  "qa_pairs": [
    {
      "question": "<self-contained question; reporter code preserved>",
      "answer": "<1-4 sentence answer grounded strictly on the thread>",
      "knowledge_type": "parametric" | "grounded",
      "grounding_sources": ["<in-thread source the answer used>", "..."],
      "answer_grounded_in": "<comment id the answer is distilled from, e.g. c1>"
    }
  ]
}
"""


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def chat_json(model: str, system: str, user: str, max_tokens: int = 6000) -> dict:
    if model.startswith("ollama/"):
        model = "ollama_chat/" + model[len("ollama/"):]
    kwargs = dict(model=model,
                  messages=[{"role": "system", "content": system},
                            {"role": "user", "content": user}],
                  max_tokens=max_tokens, reasoning_effort="low", response_format={"type": "json_object"})
    try:
        r = litellm.completion(temperature=0, **kwargs)
    except litellm.BadRequestError as exc:
        if "temperature" in str(exc).lower():
            r = litellm.completion(**kwargs)
        else:
            raise
    raw = (r.choices[0].message.content or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"non-JSON from {model}: {raw[:200]}") from exc


# ---------------------------------------------------------------------------
# Per-thread synthesis
# ---------------------------------------------------------------------------

def fix_leak_flags(question: str, hard_facts: dict, context_text: str = "") -> list[str]:
    """Flag fix-type identifiers (the answer's resolution) leaked into the question.

    A leak is the LLM pulling resolution info from the ANSWER into the normalized
    question. A fix value the reporter/community already stated BEFORE the answer is
    legitimate context the developer provided, not a leak — so we only flag a value
    that appears in the question but NOT in the pre-answer context.
    Subject identifiers (cve/ghsa/cwe/affected_versions) are legitimate context."""
    fix_fields = ("fixed_versions", "fix_prs", "fix_commits", "advisory_urls")
    leaked = []
    ql = question.lower()
    cl = context_text.lower()
    for field in fix_fields:
        for val in (hard_facts or {}).get(field, []) or []:
            v = str(val).lower()
            if val and v in ql and v not in cl:
                leaked.append(f"{field}:{val}")
    return leaked


def answer_states_fix(answer_body: str, hard_facts: dict) -> list[str]:
    """Fix-resolution facts the ANSWER itself states: a fixed version, fix PR/commit, or
    advisory the maintainer points to. Matching against the answer text — not the
    pair-level hard_facts — ties grounding to the answer and keeps reporter-cited SUBJECT
    facts out of it. A fix the answer states is repo/advisory-specific information an LLM
    cannot produce without that source, so its presence makes the pair `grounded`."""
    ab = (answer_body or "").lower()
    stated = []
    for field in ("fixed_versions", "fix_prs", "fix_commits", "advisory_urls"):
        for val in (hard_facts or {}).get(field, []) or []:
            needle = str(val).lower().lstrip("#")
            if needle and needle in ab:
                stated.append(str(val))
    return stated


def synthesize_thread(thread: dict, model: str) -> dict:
    parsed = chat_json(model, NORMALIZE_PROMPT, build_thread_view(thread))
    raw_pairs = parsed.get("qa_pairs") or []
    if not isinstance(raw_pairs, list) or not raw_pairs:
        raise ValueError("model returned no qa_pairs")

    answer_body = (comment_by_id(thread, thread.get("answer_comment_id")) or {}).get("body", "")
    answer_refs = detect_refs(answer_body)
    hard_facts = thread.get("hard_facts") or {}
    # Text the reporter/community provided before the maintainer answered — the only
    # source the question may legitimately draw on. Fix identifiers present here are
    # the questioner's own context, not a leak from the answer.
    context_text = "\n".join(c.get("body", "") for c in context_before_answer(thread))
    # Fix facts the answer itself states — the principled grounded signal (see helper).
    answer_fix_facts = answer_states_fix(answer_body, hard_facts)

    qa_pairs, leak_flags = [], []
    for i, p in enumerate(raw_pairs):
        question = str(p.get("question", "")).strip()
        answer = str(p.get("answer", "")).strip()
        if not question or not answer:
            continue
        # Drop self-referential "sources" (the answer's own comment is not a source).
        answer_cid = thread.get("answer_comment_id") or ""
        sources = [s for s in (p.get("grounding_sources") or [])
                   if str(s).strip().lower().lstrip("comment ").strip() != answer_cid.lower()
                   and not re.fullmatch(r"(comment\s+)?c\d+", str(s).strip(), re.I)]

        ktype = p.get("knowledge_type")
        if ktype not in ("parametric", "grounded"):
            ktype = "grounded" if (sources or answer_fix_facts) else "parametric"
        # A fix the ANSWER itself states (this project's version/PR/commit/advisory) is
        # repo/advisory-specific knowledge an LLM cannot produce unaided: the pair is
        # grounded regardless of the model's label, which corrects the failure mode where
        # a terse "fixed in <version>" answer is mislabelled parametric.
        if answer_fix_facts:
            ktype = "grounded"
            if not sources:
                sources = list(answer_fix_facts)
        # A grounded pair must rest on something external; if nothing remains, the answer
        # was given from general knowledge — it is parametric, whatever the model said.
        if ktype == "grounded" and not sources:
            ktype = "parametric"
        if ktype == "parametric":
            sources = []
        pair_leaks = fix_leak_flags(question, hard_facts, context_text)
        leak_flags += pair_leaks
        qa_pairs.append({
            "qid": f"{thread['id']}#{i+1}",
            "question": question,
            "answer": answer,
            "knowledge_type": ktype,
            "grounding_sources": sources,
            "answer_grounded_in": p.get("answer_grounded_in") or thread.get("answer_comment_id"),
            "leak_flags": pair_leaks,
        })

    if not qa_pairs:
        raise ValueError("no valid qa_pairs after filtering")

    return {
        "thread_id": thread["id"],
        "repo": thread.get("repo"),
        "title": thread.get("title"),
        "url": thread.get("url"),
        "source": {
            "question_comment_id": thread.get("question_comment_id"),
            "answer_comment_id": thread.get("answer_comment_id"),
            "answerer_role": thread.get("answerer_role"),
        },
        "qa_pairs": qa_pairs,
        "hard_facts": hard_facts,
        "answer_in_thread_refs": answer_refs,
        "leak_flags": leak_flags,
        "needs_review": True,          # every item awaits human verification
        "approved": False,             # human sets True
        "normalizer_model": model,
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def run(input_path: Path, output_path: Path, model: str, force: bool,
        limit: int | None) -> None:
    threads = load_jsonl(input_path)
    if limit:
        # threads = threads[:limit]
        # Use random samples
        import random
        random.seed(42)
        threads = random.sample(threads, min(limit, len(threads)))
        
    print(f"Loaded {len(threads)} threads from {input_path}")

    existing: dict[str, dict] = {}
    if output_path.exists() and not force:
        for rec in load_jsonl(output_path):
            existing[rec["thread_id"]] = rec
        print(f"Resuming: {len(existing)} already synthesized")

    results, errors = [], 0
    for i, thread in enumerate(threads):
        tid = thread["id"]
        if tid in existing and not force:
            results.append(existing[tid])
            continue
        print(f"[{i+1}/{len(threads)}] {tid} ...", end=" ", flush=True)
        try:
            rec = synthesize_thread(thread, model)
        except Exception as exc:
            print(f"ERROR: {exc}")
            errors += 1
            results.append({"thread_id": tid, "qa_pairs": [], "error": str(exc),
                            "needs_review": True, "approved": False,
                            "normalizer_model": model})
            continue
        kinds = "+".join(p["knowledge_type"][0] for p in rec["qa_pairs"])
        flag = " LEAK" if rec["leak_flags"] else ""
        print(f"{len(rec['qa_pairs'])} pair(s) [{kinds}]{flag}")
        results.append(rec)
        if i < len(threads) - 1:
            time.sleep(0.3)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        for rec in results:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    ok = [r for r in results if r.get("qa_pairs") and not r.get("error")]
    n_pairs = sum(len(r["qa_pairs"]) for r in ok)
    n_multi = sum(1 for r in ok if len(r["qa_pairs"]) > 1)
    
    kinds = Counter(p["knowledge_type"] for r in ok for p in r["qa_pairs"])
    n_leak = sum(1 for r in ok if r.get("leak_flags"))
    print(f"\nDone: {len(ok)}/{len(threads)} threads, {n_pairs} QA pairs "
          f"({n_multi} threads decomposed into >1), {errors} errors")
    print(f"Knowledge type: {dict(kinds)} | threads with fix-leak flags: {n_leak}")
    print(f"Output: {output_path}")
    print("Next: review questions/answers, then set approved:true per thread.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage 1: synthesize QA pairs from threads.")
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    run(args.input, args.output, args.model, args.force, args.limit)


if __name__ == "__main__":
    main()
