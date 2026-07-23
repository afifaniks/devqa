# SecDevQA — Evaluation Harness

A **standalone** benchmarking module. It consumes the released benchmark
`dataset/security_benchmark_final.jsonl` (plus the mined corpora as read-only data) and
writes everything to `harness/output/`. It never imports benchmark-construction code
(`eval/`, `pipeline/`) — the data is the only contract. (`llm.load_benchmark` normalizes
the thread `id` to `thread_id` and treats the final benchmark as all-approved.)

The harness web app is a **separate app** from the benchmark/open-coding review UI
(`review_ui/app.py`, port 8765). It runs on **port 8766** and lets you launch evaluations,
monitor them live, and compare runs side by side.

```
        security_benchmark_final.jsonl
                       │
        ┌──────────────┼───────────────┐
     answer          agent         coding-agent        ← systems under test
   (no_context)  (snapshot_agent)   (claude-code)
        └──────────────┼───────────────┘
                 answers_<run>.jsonl
                       │ grade
                 grades_<run>.jsonl
                       │
       monitor.py (FastAPI) ── serves ──> ui/ (React app: Monitor + Compare)
```

## Quick start

Always use the project conda Python (`/local/home/amamun/envs/devqa/bin/python`).

```bash
# 1. Run a system under test → harness/output/answers_<run>.jsonl
python -m harness answer    --model openai/gpt-5.4-mini --condition no_context
python -m harness agent     --model openai/gpt-5.4-mini           # built-in snapshot agent
python -m harness coding-agent --agent claude-code               # containerized claude-code

# 2. Grade (the judge must differ from the candidate)
python -m harness grade --answers harness/output/answers_gpt-5.4-mini_no_context.jsonl \
                        --judge gpt-5.4                            # → grades_<run>.jsonl

# 3. Build the web app once, then launch · monitor · compare
cd harness/ui && npm install && npm run build && cd -
python -m harness ui                                              # → http://localhost:8766
```

Smoke-test any run with `--limit 3 --include-unapproved`.

## Run naming

A *run* is one `(model, condition)` pair. The condition encodes the context regime:

| Condition | Meaning |
|---|---|
| `no_context` | bare LLM, parametric knowledge only |
| `snapshot_agent` | built-in agent over the full time-capped snapshot |
| `snapshot_agent-only_<group>` | single-artifact provision (RQ3) |
| `snapshot_agent-no_<group>` | leave-one-out provision (RQ3) |
| `snapshot_agent-groups_<a>_<b>` | a chosen subset of artifact groups |
| `coding_agent_<agent>` | off-the-shelf coding agent, containerized over the unified MCP snapshot (`claude_code`) |

Files are keyed by run name: `answers_<run>.jsonl`, `grades_<run>.jsonl`,
`transcripts/<run>/<qid>.json` (agent step-by-step traces).

## Web app

The UI is a **Vite + React + Mantine** single-page app under `harness/ui/` (see
[`harness/ui/README.md`](ui/README.md) for the component layout and dev workflow).
`monitor.py` (FastAPI) exposes the API, serves the built bundle, and spawns CLI runs.

```bash
python -m harness ui              # serves harness/ui/dist on :8766
python -m harness ui --port 9000
```

If the bundle isn't built, the page shows a short build hint instead of erroring.

### Benchmark tab — browse the released QA pairs
The default tab: a dataset browser over `security_benchmark_final.jsonl`. An overview
(pair/repo counts, knowledge-type donut, artifact distribution), filters (repo, knowledge
type, artifact, free-text, *has verifiable ID*), and a paginated list. Click a pair for a
detail/reading view: rendered-Markdown question + gold answer with hard facts and grounding
sources, the full issue thread (question/answer comments highlighted), and a metadata
sidebar (authors, role, artifacts, labels, dates, confidence, author note).

### Monitor tab — run evaluations, live
- **Launcher** — pick a system, model, artifact-group context, limit, and optional
  auto-grading. The model and judge are grouped-by-provider dropdowns (OpenAI / Anthropic
  / Ollama) whose options live in `models.json` — edit that file to change the suggestions
  (picked up on the next page load, no restart); any custom `provider/model` id can still
  be typed. The server spawns the matching `python -m harness …` CLI as a logged
  subprocess (`output/logs/`), so anything you do in the UI is reproducible from the
  shell. The process appears below with a **live-streaming log** and a stop button.
- **Runs** — every `answers_*`/`grades_*` file, polled live (3s). A verdict spine colors
  each card by dominant outcome; live runs pulse. Expand a run to stream its per-item
  question/response, deterministic hard-fact tier, judge claims, hallucination flags, and
  (for agents) the tool-call transcript.

### Compare tab — predictions side by side
Select two or more runs; the matrix polls live (5s) so in-flight runs fill in as they go.
- **Filters** — knowledge type, outcome (any run), repo, free-text search,
  *only disagreements*, *only graded*.
- **Statistics** — per-run stat cards (composition ring + partial-credit score, strict
  accuracy, hallucination rate, hard-fact match, avg tool calls) plus charts over the
  filtered set: accuracy by knowledge type, hard-fact match rate, and tool calls by
  artifact group (agent runs). All recompute as you filter.
- **Grid** — one row per question, one column per run; each cell shows the verdict badge,
  tool/runtime meta, and a response snippet. Expand a row for the full question, the
  **gold maintainer answer** with hard facts + grounding, and a per-run panel (full
  response, hard-fact tier, judge claims, hallucinations, flags, transcript).

## HTTP API (read-only monitoring + compare + launcher)

| Endpoint | Purpose |
|---|---|
| `GET /api/benchmark` | all QA pairs (list fields) + filter facets |
| `GET /api/benchmark/item?qid=` | full detail for one QA pair (question/answer/thread/metadata) |
| `GET /api/runs` | all runs with done/graded counts, outcome tallies, tool-group totals |
| `GET /api/runs/{name}` | recent items for one run (answer + grade joined) |
| `DELETE /api/runs/{name}` | delete a run's answers/grades/transcripts (refused while active) |
| `GET /api/compare?runs=a,b,c` | per-question matrix across runs + gold answer |
| `GET /api/transcript/{name}/{qid_slug}` | one agent transcript |
| `GET /api/options` · `POST /api/launch` · `GET /api/procs` · `POST /api/procs/{id}/stop` | launcher |

## Files

| Module | Role |
|---|---|
| `answer.py` | bare-LLM `no_context` condition |
| `agent.py` | built-in `snapshot_agent`; `--groups/--without/--only` selective provision (RQ3) |
| `container/run.py` | containerized claude-code over the unified MCP snapshot (condition `coding_agent_<agent>`), egress-locked |
| `snapshot.py` | time-capped snapshot: repo at commit-before-report, issues/PRs/advisories ≤ report time |
| `tools.py` | one tool group per artifact type (code/commits/issues/prs/advisory); call counts = RQ4 attribution |
| `grade.py` | condition-aware deterministic hard-fact tier + per-claim LLM judge; hallucination reported separately |
| `monitor.py` | FastAPI app: launcher + monitor + compare APIs; serves `ui/dist` |
| `models.json` | launcher model/judge dropdown suggestions (LiteLLM ids by provider) |
| `ui/` | Vite + React + Mantine web app (see `ui/README.md`) |
| `llm.py` | shared LiteLLM/JSONL helpers (keeps the harness dependency-light) |
| `output/` | `answers_*.jsonl`, `grades_*.jsonl`, `transcripts/`, `logs/` |
| `cache/` | repo clones, worktrees, advisory indexes, sandboxes (gitignored) |

## Notes

- The judge is **condition-aware**: internal facts (fix PRs/commits, fixed versions) are
  never scored as no-context misses; `snapshot_agent*` / `coding_agent_*` count as with-context.
- Containerized claude-code is egress-locked to the snapshot; the open-internet `+web`
  condition is opt-in and reported as such.
- Still open (see `PLAN.md` Phase 4): the `fix_reference` diff oracle, per-fact
  `knowable_at_report` temporal gating, judge ensemble + human-κ calibration.
