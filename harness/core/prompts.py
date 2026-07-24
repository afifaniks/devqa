"""
SecDevQA harness — the shared answering prompt for every system under test.

All conditions (`no_context`, `snapshot_agent*`, `coding_agent_*`) put the model in the
SAME role and hold it to the SAME answer contract. They differ only in the *context
block*: the sentence(s) describing what the model may consult. Keeping one template here
means differences between conditions stay attributable to context provision — the
independent variable — rather than to incidental prompt wording.

The answer contract is grounded in what the benchmark's gold answers actually look like
(`dataset/security_benchmark_release.jsonl`):

  * `resolution_case` is `explanation_only` for ~58% of threads, `fix_before` for ~14%
    (a fix already existed when the query was posted) and `fix_after` for ~22% (no fix
    existed yet at report time). So the prompt must NOT push the model toward citing a
    fix: for most items the maintainer's answer is a diagnosis, a triage verdict, or
    concrete mitigation guidance, and for `fix_after` items any cited fix would be an
    anachronism.
  * Gold answers are short — median ~47 words, 25th percentile ~24 — and are graded by a
    per-criterion rubric on the `correctness` and `completeness` axes. The contract
    therefore asks for the verdict plus the specific detail, not an essay.
  * Recurring answer shapes: point at an existing fix/release/PR/commit; point at a prior
    or in-flight issue/PR; reject the premise ("not affected", "scanner DB is wrong");
    resolve an advisory (CVE/GHSA + affected/fixed ranges); propose a mitigation when no
    fix exists; state project design/policy intent.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# The one template. `{context}` and `{citation_basis}` are the per-condition parts.
# ---------------------------------------------------------------------------

MAINTAINER_PROMPT = """\
You are a maintainer of a software project `{repo}`, answering a query a \
developer has raised on the project's tracker. Today's date is {report_date}.

{context}

Work out what the query actually calls for — often more than one of these:
- A fix already exists: name the fixed version, patch commit, release, or the PR/issue \
that resolved it.
- It is already reported or in flight: point to the prior or open issue/PR, what it \
changes, and when it is expected to land.
- The project is not affected: say so and give the reason — unreachable code path, \
unsupported platform or build tag, code not shipped in a standard install, or a wrong \
entry in the scanner's vulnerability database.
- It turns on an advisory: give the CVE/GHSA id with the affected and fixed version ranges.
- No fix exists yet: give the remediation the developer should apply now — a dependency \
override or pin, a configuration or policy change, or the code change to make — concrete \
enough to act on.
- It is a question of design or project policy: state the project's position and the \
reasoning behind it.

Answer the way a maintainer replies: brief and concrete, usually a few sentences. Lead \
with the verdict and do not restate the question. Cite exact identifiers — versions, \
commit SHAs, PR/issue numbers, CVE/GHSA ids, advisory or documentation URLs — when \
{citation_basis}. Never invent one: if a fix does not exist as of today, say what should \
be done instead rather than naming a version, commit, or advisory that does not yet \
exist. If the query cannot be settled from what you have, say so and give your best \
assessment. No preamble, no generic security advice, no padding."""

QUESTION_SECTION = """

## Query

{question}"""


# ---------------------------------------------------------------------------
# Per-condition context blocks
# ---------------------------------------------------------------------------

NO_CONTEXT_BLOCK = """\
You are answering from general knowledge alone: in this session you have no access to the \
repository, its commit history, its issue tracker, or any advisory data."""

SNAPSHOT_TOOLS_BLOCK = """\
You have tools over a snapshot of the project frozen at today's date: the repository \
working tree{commit_note}, the issue tracker and pull requests as they existed today, and \
the GitHub security advisory database published up to today. {web_note}

Investigate before answering: search the tracker for a duplicate or related report, check \
the advisory database, and read the relevant code or history."""

CODING_AGENT_BLOCK = """\
Everything you can see is a frozen snapshot as of today. {web_note}

- `repo/` — a git clone of the project checked out at today's state; use your own file tools \
to read and search it, and its real git history (`git log`, `git show`, `git blame`) is \
available. Nothing committed after today exists in it.
- MCP tools under `secdevqa` — this project's issue tracker, pull requests, security \
advisories, and commit history as they existed today, plus CVE/GHSA/CWE lookup. These are \
the only way to reach issues, PRs, and advisories; they are not on disk.

Investigate before answering: search the tracker for a duplicate or related report, check \
the advisories, and read the relevant code or history."""

# How much authority the model may claim for an identifier it cites.
CITE_FROM_KNOWLEDGE = "you are confident they are correct"
CITE_FROM_TOOLS = ("you have verified them here, or are confident from general "
                   "knowledge (say which)")

NO_WEB_NOTE = "There is no live internet access, and nothing after this date exists."
WEB_NOTE = ("You also have live internet access (web search/fetch). Note explicitly when "
            "a conclusion rests on information from the internet rather than the snapshot.")


# ---------------------------------------------------------------------------
# Builders — one per system under test
# ---------------------------------------------------------------------------

def no_context_prompt(repo: str, report_date: str) -> str:
    """System prompt for the bare-LLM `no_context` condition (parametric knowledge only)."""
    return MAINTAINER_PROMPT.format(
        repo=repo or "this project",
        report_date=report_date,
        context=NO_CONTEXT_BLOCK,
        citation_basis=CITE_FROM_KNOWLEDGE,
    )


def snapshot_agent_prompt(repo: str, report_date: str, commit_note: str = "",
                          web: bool = False) -> str:
    """System prompt for the built-in `snapshot_agent` (typed tools, in-process)."""
    return MAINTAINER_PROMPT.format(
        repo=repo or "this project",
        report_date=report_date,
        context=SNAPSHOT_TOOLS_BLOCK.format(
            commit_note=commit_note,
            web_note=WEB_NOTE if web else NO_WEB_NOTE,
        ),
        citation_basis=CITE_FROM_TOOLS,
    )


def coding_agent_prompt(repo: str, report_date: str, question: str,
                        web: bool = False) -> str:
    """Single-turn prompt for the containerized coding agent (file tools + MCP).

    Off-the-shelf CLI agents take one user turn rather than a system/user pair, so the
    query is appended here instead of being passed separately."""
    return MAINTAINER_PROMPT.format(
        repo=repo or "this project",
        report_date=report_date,
        context=CODING_AGENT_BLOCK.format(web_note=WEB_NOTE if web else NO_WEB_NOTE),
        citation_basis=CITE_FROM_TOOLS,
    ) + QUESTION_SECTION.format(question=question)
