# SecDevQA

**A benchmark of real developer security queries and the context needed to answer them.**

A *security query* is a developer's security information need as it surfaces in a project
thread — whether posed as an explicit question or raised as a vulnerability/bug report whose
resolution they need. SecDevQA mines such query–answer exchanges from open-source GitHub
issue and discussion threads, normalizes each into a self-contained, resolution-free
evaluation item (with GPT-5.5), and grades LLMs/agents on them under controlled context
conditions. Pairs are **not** filtered on carrying a verifiable fact; each is labeled by
**knowledge type** (parametric vs grounded) and by whether the maintainer's answer cites an
**external reference** (CVE/GHSA/CWE ID, fixed version, fix PR/commit, advisory/issue/
documentation link) or answers from explanation alone.

- Research design: [`research_plan_v6.md`](research_plan_v6.md) (plan of record) and
  [`methodology_review.md`](methodology_review.md) (normalization & grading methodology).
- Progress assessment and roadmap: [`PLAN.md`](PLAN.md).
- Detailed mining/labelling guide: [`README_SECURITY.md`](README_SECURITY.md).
- The repo also contains a legacy general-dev-questions taxonomy pipeline (Q1–Q78), documented
  in [`docs/README_legacy_taxonomy_pipeline.md`](docs/README_legacy_taxonomy_pipeline.md);
  it is not part of SecDevQA.

---

## Pipeline at a glance

```
Step 0  dataset/repo_selector.py            GitHub Advisory DB → repo_candidates.csv
Step 1  pipeline/run_all.py                 mine issues/PRs/commits → output/<owner>__<repo>/
Step 2  pipeline/classification/
            detect_security_qa.py           threads → security_qa_pairs.jsonl (LLM, 2-stage)
Step 3  review UI  /security                human accept/reject → security_verified_state.json
Step 4  dataset/build.py                    accepted pairs → dataset/security_benchmark.jsonl
Step 5  open_coding/open_code.py            LLM open codes → dataset/open_codes.jsonl
Step 6  review UI  /open-coding             human verify codes → open_codes_verified.json
Step 7  filter_benchmark_data.py            benchmark ∩ accepted codes → security_benchmark_filtered.jsonl
Step 8  dataset/synthesize.py (Stage 1)     threads → self-contained QA items → dataset/eval_pairs.jsonl
Step 9  review UI  /normalized              human approve items (approved: true)
Step 10 harness  answer|agent|external      systems under test answer, per condition
Step 11 harness  grade                      condition-aware deterministic tier + per-claim LLM judge
Step 12 harness  ui                         web UI: launch runs + live monitoring (port 8766)
```

Steps 3, 6, and 9 are human-in-the-loop; everything else is scripted and resumable.

---

## Setup

**Python environment** — a conda env at `/local/home/amamun/envs/devqa`. Always invoke it by
full path (the login shell is tcsh; don't rely on `conda activate`):

```bash
/local/home/amamun/envs/devqa/bin/python --version
```

To recreate it: `conda create -p <path> python=3.11` then
`pip install fastapi 'uvicorn[standard]' python-dotenv requests tqdm litellm anthropic openai`.

**Credentials** — a `.env` file at the project root:

```
GITHUB_TOKEN=ghp_...            # or GITHUB_TOKENS=ghp_a,ghp_b for higher mining throughput
OPENAI_API_KEY=sk-...           # normalization / answering / judging via LiteLLM
ANTHROPIC_API_KEY=sk-ant-...    # optional, for Claude models
```

**Ollama (optional)** — only needed to run local open-weight models
(`ollama serve`, then pass e.g. `--model ollama/qwen3.6:latest` to any LLM stage).

All LLM stages take LiteLLM model ids: `openai/gpt-5.4-mini`, `anthropic/claude-sonnet-4-6`,
`ollama/<model>`, etc.

Shorthand used below: `PY=/local/home/amamun/envs/devqa/bin/python`.

---

## Step 0 — Select repositories to mine

Requires a local clone of the [GitHub Advisory Database](https://github.com/github/advisory-database)
at `./advisory-database` (or pass `--advisory-db`).

```bash
git clone --depth 1 https://github.com/github/advisory-database
$PY dataset/repo_selector.py \
    --min-fixed-advisories 10 --min-stars 1000 \
    --max-months-since-push 24 --top-per-ecosystem 5
```

Output: `repo_candidates.csv` (+ `selection_summary.txt`). Pick repos from it and add them to
`REPOS` in `pipeline/config.py`.

## Step 1 — Mine a repository

```bash
cd pipeline
$PY run_all.py --repo owner/repo            # full mining (issues, PRs, commits, CI, threads)
$PY run_all.py --repo owner/repo --skip-ci  # skip slow CI mining on big repos
# security pipeline only needs threads; this is enough after issues are mined:
$PY miners/mine_threads.py --repo owner/repo
```

Output: `output/owner__repo/` (`issues.jsonl`, `raw_threads.jsonl`, ...). Mining is
checkpointed via hidden `.checkpoint_*.json` files; re-running resumes.

## Step 2 — Detect security query–answer pairs

Two-stage LLM detector with regex hard-fact pre-pass and an anchor acceptance gate
(see `README_SECURITY.md` for the full stage diagram and tuning knobs).

```bash
cd pipeline
$PY classification/detect_security_qa.py --repo owner/repo \
    --stage1-samples 3            # N-sample self-consistency for Stage 1
# useful flags: --limit N  --max-pairs N  --state open|closed  --since/--until YYYY-MM-DD
#               --confidence 0.5  --model <litellm-id>  --force
```

Output: `output/owner__repo/security_qa_pairs.jsonl`. Checkpointed and resumable.

## Steps 3 / 6 / 9 — Human review UI

One FastAPI app serves every review surface:

```bash
cd review_ui
$PY app.py            # → http://localhost:8765
```

| Page | Purpose | State file |
|---|---|---|
| `/security` | **Step 3** — accept/reject detected pairs | `security_verified_state.json` |
| `/open-coding` | **Step 6** — verify/edit LLM open codes | `dataset/open_codes_verified.json` |
| `/normalized` | **Step 9** — approve normalized eval items | writes back to `dataset/eval_pairs.jsonl` |
| `/benchmark` | browse/edit `security_benchmark.jsonl` records | the benchmark file itself |
| `/security/chat` | LLM-assisted pair review | — |
| `/stats`, `/taxonomy` | dashboards / reference | — |

Keyboard: `j`/`k` navigate, `a` accept, `r` reject, `u` reset. Decisions save immediately.
Labelling criteria (what to accept/reject) are documented in `README_SECURITY.md`.

## Step 4 — Build the benchmark

Collects all `accepted` pairs from the verification state into the primary artifact:

```bash
$PY dataset/build.py        # → dataset/security_benchmark.jsonl
```

Re-run this whenever new reviews are added (the file is otherwise stale).
Edit individual records only via the `/benchmark` UI, never by hand.

## Step 5 — Open coding (taxonomy, RQ1)

Assigns 1–2 inductive codes per pair toward the security-query taxonomy:

```bash
$PY open_coding/open_code.py --model openai/gpt-5.4-mini          # → dataset/open_codes.jsonl
$PY open_coding/open_code.py --model openai/gpt-5.4-mini --limit 5  # smoke test
# also: --force, --output <file>, --api-base <url> (for ollama)
```

Resumable (skips already-coded ids). Then verify in `/open-coding` (Step 6) and export.

## Step 7 — Build the verified evaluation set

Joins the benchmark with accepted open codes:

```bash
rm -f dataset/security_benchmark_filtered.jsonl   # the script appends — clear first
$PY dataset/filter_benchmark_data.py                       # → dataset/security_benchmark_filtered.jsonl
```

## Step 8 — Synthesize threads into eval items (Stage 1)

Converts each verified thread into one or more **self-contained, resolution-free**
(query, answer) items, labels each with a **knowledge type** (`parametric` vs `grounded`
— the answerability axis, hardened by a deterministic fix-fact rule), records
`grounding_sources`, and flags answer leaks deterministically. See
`methodology_review.md` for the rationale.

```bash
$PY -m dataset.synthesize                          # → dataset/eval_pairs.jsonl
$PY -m dataset.synthesize --limit 5 --model openai/gpt-5.5
```

Then human-review every item in `/normalized` (Step 9) until threads have `approved: true`.

## Step 10 — Run systems under test (harness)

Benchmarking lives in the standalone **`harness/`** package — it consumes
`dataset/eval_pairs.jsonl` as a data file and never imports construction code.
Three system types:

**`no_context`** — bare LLM, query only:

```bash
$PY -m harness answer --model openai/gpt-5.4-mini --condition no_context
# smoke test without approvals: --limit 3 --include-unapproved
```

**`snapshot_agent`** — built-in agent with typed tools over a **time-capped snapshot**:
the repository checked out at the last commit before the report, the issue/PR corpus up
to the report time (the question's own thread excluded), and the GHSA advisory database
published up to the report time. No live web. One tool group per artifact type
(`code`, `commits`, `issues`, `prs`, `advisory`), so consulted artifact types are
tool-call counts (RQ4):

```bash
$PY -m harness agent --model openai/gpt-5.4-mini                    # full snapshot
$PY -m harness agent --model openai/gpt-5.4 --without advisory      # leave-one-out (RQ3)
$PY -m harness agent --model openai/gpt-5.4 --only advisory         # single-artifact (RQ3)
$PY -m harness agent --model openai/gpt-5.4 --groups code,issues    # arbitrary subset
# flags: --limit N  --include-unapproved  --max-steps 15  --force
```

**`external_*`** — off-the-shelf coding agents (Claude Code, OpenCode) run headlessly in
a per-item **time-capped sandbox**: `repo/` exported at the snapshot commit (no `.git`,
so no post-report history), plus `data/{issues.jsonl,prs.jsonl,advisories.json,
commit_log.txt}` capped at report time, and a `QUESTION.md` with ground rules:

```bash
$PY -m harness external --agent claude-code --limit 1 --include-unapproved
$PY -m harness external --agent opencode --model anthropic/claude-sonnet-4-6
# flags: --timeout 600  --keep-sandbox  --agent-args "..."
```

> Caveat (report in threats-to-validity): external agents with a shell cannot be
> *provably* time-capped — the prompt forbids web access and the sandbox has no git
> history, but only the built-in typed-tool agent is airtight.

First use of a repo clones it (blobless, full history) into `harness/cache/repos/` and
indexes the advisory database — both cached and reused. Agent transcripts land in
`harness/output/transcripts/<run>/<qid>.json`.

Output: `harness/output/answers_<run>.jsonl`, resumable per question id.

## Step 11 — Grade (eval Stage 3)

Two tiers (plan §3.4): a **condition-aware deterministic hard-fact tier** (project-internal
facts — fix PRs/commits, fixed versions — are *never* counted as no-context misses; subject
facts — CVE/GHSA/CWE — grade under any condition) and a **per-claim LLM judge** that verdicts
each gold claim yes/partial/no with quoted evidence and reports hallucinated specifics
separately.

```bash
$PY -m harness grade \
    --answers harness/output/answers_openai-gpt-5.4-mini_no_context.jsonl \
    --judge gpt-5.4                                # judge must differ from the candidate
```

Output: `harness/output/grades_*.jsonl` + a summary (outcomes by knowledge type,
hallucination rate, hard-fact recall, judge-vs-regex cross-check flags for human
spot-checking). The judge is condition-aware: tool-derived enrichment under agent
conditions is not flagged as hallucination, and internal facts are never no-context misses.

## Step 12 — Harness web UI (launch + live monitoring)

A standalone React single-page app served by FastAPI (no build step; separate from the
review UI):

```bash
$PY -m harness ui                # → http://localhost:8766
```

- **Launch panel** — pick the system (bare LLM / built-in snapshot agent / claude-code /
  opencode), model, artifact-group context selection, limit, force, and optional
  auto-grading with a judge; the server spawns the exact `python -m harness ...` CLI as
  a logged subprocess (`harness/output/logs/`), so every UI action is reproducible from
  the shell. Launched processes can be watched (live log tail) and stopped.
- **Monitor** — live run cards (3s poll): progress, errors, outcome distribution,
  hallucination counts, per-artifact-group tool usage; click into any item for the
  question, response, deterministic hard-fact matches, judge claims, and the full agent
  transcript. Read-only over the JSONL files — runs need no coordination with it.

---

## Repository layout

```
dataset/
  security_benchmark.jsonl           primary artifact (accepted pairs, full threads)
  security_benchmark_filtered.jsonl  ∩ accepted open codes — input to normalization
  eval_pairs.jsonl                   normalized eval items (Stage 1 output + review state)
  open_codes.jsonl / *_verified.*    open coding outputs and verification state
  build.py / repo_selector.py
pipeline/
  config.py, run_all.py              mining orchestration
  miners/                            issues, PRs, commits, CI, contributors, threads
  classification/detect_security_qa.py   the security query–answer detector
  utils/                             GitHub client, LLM clients, storage, (legacy) taxonomy
open_coding/open_code.py             LiteLLM open coding
harness/                             standalone benchmarking module (no dataset/pipeline imports)
  answer.py                          bare-LLM no_context condition
  agent.py                           built-in snapshot_agent (typed tools, --groups/--without/--only)
  external.py                        external agents (claude-code, opencode) in time-capped sandboxes
  snapshot.py                        time-capped snapshot assembly (repo/issues/PRs/advisories)
  tools.py                           typed tool groups + selective-provision gating
  grade.py                           condition-aware grading (deterministic tier + judge)
  monitor.py + ui.html               web UI: launcher + live monitor (React, port 8766)
  llm.py                             shared LiteLLM/JSONL helpers
  __main__.py                        python -m harness {answer,agent,external,grade,ui}
  output/                            answers_*.jsonl, grades_*.jsonl, transcripts/, logs/
  cache/                             repo clones, worktrees, advisory indexes, sandboxes (gitignored)
review_ui/app.py                     all human-review surfaces (port 8765)
output/<owner>__<repo>/              per-repo mined data (only security_qa_pairs.jsonl is tracked)
paper_draft/                         ICSE paper (LaTeX)
advisory-database/                   local GitHub Advisory DB clone (Step 0)
```

Conventions: `repo` fields are `owner/repo`; output folders are `owner__repo`. All data files
are JSONL. Checkpoints are hidden `.checkpoint_*.json` files per output folder — delete them
or pass `--force` to re-run a stage from scratch.

## Data flow summary

```
security_qa_pairs.jsonl ──review──▶ security_verified_state.json ──build──▶ security_benchmark.jsonl
security_benchmark.jsonl ──open_code──▶ open_codes.jsonl ──review──▶ open_codes_verified.json
(benchmark ∩ accepted codes) ──filter──▶ security_benchmark_filtered.jsonl
filtered ──normalize──▶ eval_pairs.jsonl ──review(approve)──▶ answer ──▶ grade
```
