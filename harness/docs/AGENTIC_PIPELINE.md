# The agentic pipeline (`snapshot_agent`)

How the built-in agent condition works end to end: a model under test answers each
benchmark query with autonomous, typed tool access over a **time-capped snapshot** of the
project. This is the `snapshot_agent` condition and its selective-provision variants
(RQ3/RQ4). For the harness as a whole see [`README.md`](README.md); for the external
off-the-shelf agents (`claude-code`, `opencode`) see `external.py`.

```
python -m harness agent --model ollama/qwen3.6:latest
python -m harness agent --model openai/gpt-5.4-mini --without advisory
python -m harness agent --model anthropic/claude-sonnet-4-6 --only code
```

---

## Pipeline at a glance

```
benchmark thread (id, created_at=T, repo)
        │
        ▼
build_snapshot(thread_id, groups)         harness/snapshot.py
   ├─ repo worktree @ last commit before T   (code, commits groups)
   ├─ issues created ≤ T, source thread excluded, comments capped at T
   ├─ PRs created ≤ T, reviews capped at T
   └─ GHSA advisories published ≤ T
        │
        ▼
ToolBox(snap, groups)                      harness/tools.py
   typed tools, one group per artifact type; results truncated to 5000 chars
        │
        ▼
run_streaming_agent(model, q, box, emit)   harness/stream_agent.py
   LangChain create_agent ReAct loop, streamed; LLM ↔ tool calls until the
   model answers (or --max-steps → forced final). Emits live events as it goes.
        │                                   │
        ▼                                   ▼
answers_<run>.jsonl                    transcripts/<run>/<qid>.live.jsonl  (live)
transcripts/<run>/<qid>.json           ← tailed by the monitor UI in flight
        │
        ▼
python -m harness grade --answers ...      harness/grade.py  (condition-aware)
```

`harness/agent.py` holds the **evaluation business logic** (which items to run, snapshot +
ToolBox wiring, condition naming, record + transcript writing). The **streaming execution
layer** is separated into `harness/stream_agent.py`.

---

## 1. Time-capped snapshot (`snapshot.py`)

The time cap **T** = the report time = the benchmark thread's `created_at`. Everything the
agent can see is frozen at T so the resolution cannot leak. No live web access anywhere —
a live NVD/GHSA lookup would disclose the fix and void the cap.

`build_snapshot(thread_id, groups)` materializes **only** the requested artifact groups:

| Group      | Source                                          | Time cap |
|------------|-------------------------------------------------|----------|
| `code`     | blobless clone → worktree at `commit_before(T)` | last default-branch commit before T |
| `commits`  | same worktree (history is the checkout)         | `git_show` guarded to ancestors of HEAD |
| `issues`   | `output/<repo>/issues.jsonl`                    | issues created ≤ T, comments ≤ T, **source thread excluded** |
| `prs`      | `output/<repo>/pull_requests.jsonl`             | PRs created ≤ T, reviews ≤ T |
| `advisory` | local `advisory-database` clone (GHSA)          | advisories published ≤ T |

Leak control: the question's own thread is removed (`exclude_number`), but **pre-T
duplicate/related reports stay findable** — recovering them is the retrieval task.

Caching (all reused across runs, gitignored under `harness/cache/`):
- `cache/repos/<owner>__<repo>` — one blobless clone per repo
- `cache/worktrees/<owner>__<repo>/<sha12>` — one shared worktree per (repo, commit)
- `cache/advisories/<owner>__<repo>.json` — one-time grep index of advisories per repo

The benchmark consumed is `dataset/security_benchmark_release.jsonl` if built, else
`dataset/security_benchmark_final.jsonl`.

## 2. Typed tools (`tools.py`)

One tool group per artifact type — so "which artifacts did the agent consult" is just a
count of tool calls by group (RQ4 attribution by construction).

| Group      | Tools                                   |
|------------|-----------------------------------------|
| `code`     | `list_dir`, `read_file`, `search_code`  |
| `commits`  | `git_log`, `git_show`                   |
| `issues`   | `search_issues`, `get_issue`            |
| `prs`      | `search_prs`, `get_pr`                  |
| `advisory` | `search_advisories`, `get_advisory`     |

- `TOOL_SCHEMAS` defines each tool's args schema for **active groups only** — a disabled
  group's tools are not even advertised (`build_tools` in `stream_agent.py`).
  `ToolBox.execute` double-checks the group is active before dispatch.
- Search tools are keyword-scored (`_kw_search`); `search_code` is `git grep`.
- Every result is truncated to `MAX_RESULT_CHARS` (5000). Tool errors are returned as
  `ERROR: ...` strings, never raised — a bad tool call must not kill the run.
- `_safe_path` confines file reads to the worktree; `git_show` rejects non-ancestor SHAs
  (post-T commits exist in the clone but must stay invisible).

## 3. Streaming agent loop (`stream_agent.py`)

The loop runs on **LangChain `create_agent`** (a ReAct agent on LangGraph) — the same
primitive `deepagents.create_deep_agent` wraps, but *without* deepagents' planning /
filesystem / sub-agent middleware. That matters: those middlewares inject extra tools
(`write_todos`, `ls`, `read_file`, `task`, …) into every run, which would corrupt the RQ4
tool-attribution counts and the trajectory. `create_agent` exposes only our five snapshot
tool groups and nothing else.

`run_streaming_agent(model, question, box, system_prompt, max_steps, emit)`:

1. `langchain_model(model)` maps `provider/model` → a LangChain chat model: `ollama/…` →
   `ChatOllama` (chat endpoint — tool calling requires it), `openai/…` → `ChatOpenAI`,
   `anthropic/…` → `ChatAnthropic`, else `init_chat_model`.
2. `build_tools(box)` wraps each active snapshot tool as a `StructuredTool` whose function
   routes through `ToolBox.execute` — so RQ4 call recording and result truncation are
   identical to the non-streaming path.
3. `agent.astream_events(version="v2")` is consumed: `on_tool_start` / `on_tool_end` build
   the trajectory and live events; `on_chat_model_stream` emits answer tokens;
   `on_chat_model_end` with no tool calls is the final answer.
4. `--max-steps` (default 15) maps to a LangGraph `recursion_limit`; on
   `GraphRecursionError` the conversation is replayed once with "out of tool budget, answer
   now" and **no tools** for a forced final.

**Live events.** As each event arrives, `emit({...})` is called. `agent.py` passes a
`file_emitter` that appends events to `transcripts/<run>/<qid>.live.jsonl` and flushes, so
the monitor UI can tail an item *while it runs* (see §7). Event types: `start`,
`tool_call`, `tool_result`, `token`, `final` / `final_forced`, `done`.

**No output-token cap.** Thinking models (e.g. Ollama qwen3) spend their budget on a
reasoning trace *before* emitting the answer; an output cap truncates them mid-reasoning
and yields an empty response. `_text_of(...)` reads message `content`, falling back to
`reasoning_content`. (Anthropic's API *requires* `max_tokens`; it gets a generous 8192
default — a provider constraint, not our cap.)

> Ollama caveat: the default `num_ctx` can be small enough to truncate the *input* on long
> transcripts, silently dropping the system prompt or tools. If long runs degrade, raise
> `OLLAMA_CONTEXT_LENGTH` / `num_ctx`.

## 4. Selective provision (RQ3) — which artifacts

The condition name encodes the active groups, keeping grading condition-aware:

| Flag                       | Groups enabled                | Condition name                       |
|----------------------------|-------------------------------|--------------------------------------|
| (none)                     | all five                      | `snapshot_agent`                     |
| `--without advisory`       | all but one (leave-one-out)   | `snapshot_agent-no_advisory`         |
| `--only code`              | one only (single-artifact)    | `snapshot_agent-only_code`           |
| `--groups code,issues`     | explicit subset               | `snapshot_agent-groups_code+issues`  |

`--only` and `--without` are mutually exclusive; `--groups` overrides both. Disabled
groups are not materialized in the snapshot **and** their tools are not exposed.

## 5. Outputs

- `harness/output/answers_<slug(model)>_<condition>.jsonl` — one record per query:
  `qid`, `thread_id`, `repo`, `condition`, `model`, `knowledge_type`, `question`,
  `response`, `snapshot` (commit, report_time, counts), `tool_calls_by_group`,
  `n_tool_calls`. Resumable: a rerun skips qids already answered without error
  (use `--force` to overwrite).
- `harness/output/transcripts/<run>/<qid>.json` — full step-by-step transcript (every
  tool call with args and result, plus the final/forced-final marker). Written once the
  item finishes; format unchanged by the streaming rework.
- `harness/output/transcripts/<run>/<qid>.live.jsonl` — the live event log written *during*
  the run (one JSON event per line). Transient; the canonical `.json` above is the record.

## 6. Grading

```
python -m harness grade --answers harness/output/answers_<run>.jsonl --judge gpt-5.4
```

Grading is **condition-aware**: any `snapshot_agent*` (and `external_*`) condition counts
as a with-context condition, so internal facts the agent could retrieve (fix PRs/commits,
fixed versions) are not scored as no-context misses, and tool-derived enrichment is not
counted as hallucination. The judge must differ from the candidate model.

## Common invocations

```bash
# smoke test: 3 items, shallow budget, include unapproved, overwrite
python -m harness agent --model ollama/qwen3.6:latest \
    --limit 3 --include-unapproved --max-steps 6 --force

# full run, leave-one-out (no advisory)
python -m harness agent --model openai/gpt-5.4-mini --without advisory

# single-artifact (code only)
python -m harness agent --model openai/gpt-5.4 --only code

# then grade
python -m harness grade \
    --answers harness/output/answers_gpt-5.4-mini_snapshot_agent-no_advisory.jsonl \
    --judge gpt-5.4
```

## Flags (`python -m harness agent --help`)

| Flag                  | Default                  | Meaning                                   |
|-----------------------|--------------------------|-------------------------------------------|
| `--model`             | (required)               | `provider/model` id; must support tool calls |
| `--without`           | —                        | comma list of groups to drop (LOO)        |
| `--only`              | —                        | enable a single group                     |
| `--groups`            | —                        | explicit comma list (overrides the above) |
| `--max-steps`         | 15                       | tool-calling rounds before forced final   |
| `--limit`             | all                      | cap number of items                       |
| `--include-unapproved`| off                      | include non-approved benchmark items      |
| `--force`             | off                      | overwrite instead of resume               |
| `--input`             | release/final benchmark  | benchmark JSONL path                      |
| `--output-dir`        | `harness/output`         | output directory                          |

> There is intentionally **no `--max-tokens`** for the agent — see §3.

## 7. Live monitoring (monitor UI)

The agent emits live events while each item runs, so the monitor UI shows which tool is in
flight and what the agent is doing — not just which item.

- `stream_agent.py` appends events to `transcripts/<run>/<qid>.live.jsonl` as they happen.
- `monitor.py` serves them: `GET /api/live/<run>/<qid_slug>?since=<n>` returns the events
  after index `n` plus a `done` flag. (`<qid_slug>` = the qid with `/` → `__`.)
- The UI (`ui/src/components/LiveTimeline.jsx`) polls that endpoint (~1.5 s) for the
  in-flight `current_qid` of a running agent run and renders the tool timeline (per-group
  colour, args, result size) with streamed answer tokens. It is mounted in the process card
  (`ProcessList.jsx`) only for agent runs in the `answering` phase.

```
python -m harness ui      # http://localhost:8766 — launch a run, expand its card to watch
```

Run name detection (`isAgentRun`) limits live polling to agent runs; bare-LLM, grading, and
external-agent runs don't write a live log and aren't polled.
