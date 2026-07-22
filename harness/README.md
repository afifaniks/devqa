# SecDevQA Evaluation Harness

A self-contained benchmarking module that measures how well LLMs and coding agents answer
real developer **security queries**, under controlled context conditions. It consumes the
released benchmark (`dataset/security_benchmark_release.jsonl`) as data and writes answers,
gradings, and transcripts to `harness/output/`. It never imports the benchmark-construction
code (`eval/`, `pipeline/`).

> **Python:** always use the project env — `/local/home/amamun/envs/devqa/bin/python`.
> Throughout this README, `PY` is shorthand for that interpreter:
> ```bash
> set PY=/local/home/amamun/envs/devqa/bin/python      # tcsh
> ```

---

## 1. TL;DR — run one item end to end

```bash
# Build the container image once (rootless podman):
bash harness/container/build.sh

# Run claude-code, in an egress-locked container, over the unified MCP snapshot interface:
$PY -m harness container --agent claude-code \
    --only-id psf/requests/issue/7209#1 --include-unapproved --auth mount

# Grade the answer (judge must differ from the candidate):
$PY -m harness grade \
    --answers harness/output/answers_container_claude_code_*.jsonl \
    --judge ollama/gemma4:31b

# Or drive everything from the web UI (launch + live monitoring):
$PY -m harness ui        # → http://localhost:8766
```

---

## 2. Core concepts

### The benchmark
Each line of the benchmark is a verified GitHub issue/discussion **thread** normalized into one
or more self-contained **query–answer pairs** (`qa_pairs`), with a `qid`
(`owner/repo/issue/N#k`), a resolution-free `question`, a thread-grounded gold `answer`, a
`knowledge_type` (`parametric` | `grounded`), and `hard_facts` (CVE/GHSA/CWE ids, fixed
versions, fix PRs/commits). Rubric-bearing pairs also carry a grading rubric.

### The time cap `T`
Every "with-context" condition freezes the world at the moment the query was reported
(`thread.created_at = T`): the repository at the last commit before `T`, the issue/PR corpus up
to `T` (the **source thread excluded** — pre-`T` duplicates stay findable, that's the retrieval
task), and the GHSA advisory database published up to `T`. Nothing after `T` is visible — that
is what makes an answer an honest prediction rather than a lookup of the fix.

### Artifact groups (RQ3 selective provision)
The snapshot is split into five groups: **`code`**, **`commits`**, **`issues`**, **`prs`**,
**`advisory`**. A run can be given all of them, all-but-one (leave-one-out), or exactly one
(single-artifact). Which tools the agent can call is gated by the enabled groups.

### Conditions (systems under test)
| Condition | Command | Context |
|---|---|---|
| `no_context` | `harness answer` | bare LLM, no tools |
| `snapshot_agent[…]` | `harness agent` | built-in LangChain agent, typed tools in-process (host) |
| `external_<agent>` | `harness external` | off-the-shelf agent in a file sandbox (legacy, best-effort capped) |
| **`container_<agent>`** | **`harness container`** | **off-the-shelf agent in a per-item, egress-locked container over the unified MCP interface** ← recommended |

`container_*` is the current, airtight path and the focus of the rest of this README.

---

## 3. Architecture

```
harness/
  __main__.py            dispatch: answer | agent | external | container | grade | ui
  core/                  paths, benchmark loader, shared run plumbing (iter/select/resume/lock)
  snapshot/
    builder.py           build a time-capped Snapshot (cached blobless clone + worktree,
                         issues/PRs ≤ T, GHSA advisories ≤ T)
    tools.py             ToolBox — the ONE tool implementation: typed, group-tagged, truncated,
                         call-logged (read_file/search_code/git_log/search_issues/…/vuln_lookup)
    payload.py           on-disk Snapshot serialization contract (host ↔ container)
    stream_agent.py      LangChain ReAct loop + live events (built-in agent)
  mcp/
    server.py            FastMCP stdio server — wraps ToolBox, registers only enabled groups,
                         emits a live event per call. The UNIFIED tool interface.
    events.py            live-event writer (same schema as stream_agent → the UI's /api/live)
  container/
    materialize.py       host → container-ready snapshot payload (offline + airtight)
    egress.py            egress allowlist policy + persisted, UI-editable config
    Containerfile        the eval image (node+python+claude+opencode+MCP+firewall tooling)
    build.sh             build the image (rootless podman)
    entrypoint.sh        installs the DNS-driven egress firewall, then execs the agent
    run.py               the container runner (materialize → podman run → capture → record)
    TASK7_builtin_over_mcp.md   deferred: run the built-in agent in-container over MCP
  conditions/
    answer.py            no_context (bare LLM)
    agent.py             snapshot_agent (built-in, host, in-process ToolBox)
    external.py          external_<agent> (legacy file sandbox)
  grading/grade.py       condition-aware rubric + hard-fact grading (LLM judge)
  monitor/               FastAPI app (port 8766): launcher + run/live monitor + compare + egress API
  ui/                    Vite/React/Mantine front end (own README); build → ui/dist
  output/                answers_*.jsonl, grades_*.jsonl, transcripts/<run>/, logs/
  cache/                 repo clones, worktrees, advisory/vuln indexes, container payloads
```

**Design invariant — one tool implementation.** `ToolBox` is the single backend. The built-in
agent calls it in-process; the MCP server wraps it. There is no second implementation of
"read a file" or "search issues" to drift out of sync, and RQ4 tool-call attribution is produced
the same way everywhere.

---

## 4. How a containerized claude-code run works

`harness container --agent claude-code` runs, **per benchmark item**:

```
HOST                                         CONTAINER (podman, --rm, egress-locked)
────                                         ──────────────────────────────────────
1. materialize_payload(thread_id, groups)
   • git archive @commit → single-commit
     repo  (offline, no history to leak)
   • precompute ancestor-only commit log
     + patches (commits group)
   • dump issues/PRs/advisories as JSON
   • write mcp.json + empty live.jsonl
                    │  bind-mount ro: payload → /workspace/snapshot
                    │  bind-mount rw: live.jsonl → /workspace/live.jsonl
                    │  bind-mount ro: harness/ → /opt/secdevqa/harness
                    ▼
2. podman run … entrypoint.sh claude …  ┌─► entrypoint.sh:
                                        │     dnsmasq(allowlisted domains → ipset)
                                        │     iptables default-DROP except ipset
                                        │     → github/pypi/direct-IP BLOCKED
                                        │   claude -p "<question>" \
                                        │     --mcp-config /workspace/mcp.json \
                                        │     --strict-mcp-config \
                                        │     --output-format stream-json --verbose \
                                        │     --dangerously-skip-permissions \
                                        │     --disallowedTools WebSearch WebFetch
                                        │
                                        │   claude spawns the MCP server as a subprocess:
                                        │     python -m harness.mcp.server
                                        │       (SECDEVQA_SNAPSHOT_DIR=/workspace/snapshot,
                                        │        SECDEVQA_LIVE_EVENTS=/workspace/live.jsonl,
                                        │        SECDEVQA_GROUPS=code,commits,issues,prs,advisory)
                                        │     → tools: mcp__secdevqa__search_issues, …
                                        │     each call → live.jsonl (streamed to host)
                                        └─► claude also uses its OWN file tools over
                                            /workspace/snapshot/repo (Read/Grep/Bash)
3. stream container stdout → console
   (firewall lines, session init,
    "→ search_issues {…}", final)
4. parse stream-json → final answer +
   native tool calls; MCP live.jsonl →
   tool_calls_by_group (RQ4)
5. write answers_<run>.jsonl + transcript
```

### Why it's airtight (validity)
- **Repo:** `git archive @commit | tar x` wrapped in a fresh single-commit git repo — all files
  present offline, and `git log` shows only the snapshot commit, so even the agent's own git
  cannot reach ancestor/future history. (A `git bundle` from the blobless cache is *not*
  offline-complete — verified — hence the archive approach.)
- **Commits:** precomputed from **ancestors of the snapshot commit only**; a thread's fix commit
  usually postdates `T`, and shipping its patch would leak the resolution.
- **Network:** the entrypoint installs a DNS-driven allowlist firewall (dnsmasq populates an
  ipset with resolved IPs; iptables default-drops everything else). Verified: the model API and
  vuln-resolution hosts are reachable; **github.com, pypi, and even a direct-to-IP connection are
  blocked**. This upgrades the external condition from "best-effort capped" to enforced-at-the-
  network-layer.
- **The payload is leak-free:** it carries snapshot artifacts only, never the gold answer.

### Off-the-shelf agents keep their own tools
The repo is on disk at `/workspace/snapshot/repo`, so claude-code uses its native
`Read`/`Grep`/`Bash` for code — realistic. Issues/PRs/advisories/commits are **not** on disk;
those are reached only through the MCP `secdevqa` tools. Attribution combines both: MCP calls
from the live log + the agent's own tools parsed from `stream-json`.

---

## 5. Authentication (claude-code)

claude-code needs Anthropic credentials. The runner resolves them with `--auth`:

| `--auth` | Source | Notes |
|---|---|---|
| `mount` | your host `~/.claude` login (subscription) | copied into a per-run dir and bind-mounted, so a token refresh inside the container cannot rotate/clobber your host login; the copy is auto-deleted after the run |
| `env` | `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` | from the environment / `.env` |
| `auto` (default) | env token if present, else mounted login | |

**Subscription (recommended for dev):** either just use `--auth mount`, or mint a long-lived
token with `claude setup-token` and put `CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-…` in `.env`.

> Caveats for scaling up: a Pro subscription's rate limits will throttle a full ~180-item run
> (fine for handfuls). The subscription model id isn't pinnable the way an API `model` is — for
> citable/reproducible final numbers, consider an API key with a fixed model. Both are recorded
> as threats-to-validity.

---

## 6. Network egress allowlist

Restricted (time-capped) runs may reach only:
- the configured model providers — `anthropic.com` (+ `claude.ai`), `openai.com`
- the vuln-resolution hosts — `api.osv.dev`, `services.nvd.nist.gov`, `cwe-api.mitre.org`
  (canonical CVE/GHSA/CWE lookup is reference resolution, not a leak)
- the host Ollama (`10.0.2.2:11434`) if enabled
- any **extra domains** you add

Everything else is blocked. The config is persisted at `harness/resources/egress.json` and is
**editable from the UI** (Launcher → "Container egress allowlist"), or via the API:

```bash
curl localhost:8766/api/egress
curl -X PUT localhost:8766/api/egress -H 'Content-Type: application/json' \
  -d '{"providers":["anthropic","openai"],"extra_domains":["pypi.org"],"allow_ollama":true}'
```

New runs pick up a saved allowlist with no restart. The **`--web`** flag opts a run into open
internet (no firewall) — it intentionally breaks the time-cap and is recorded with a `+web`
condition suffix.

---

## 7. Running each command

### Setup (once)
```bash
# env vars in .env at repo root: GITHUB_TOKEN(S), OPENAI_API_KEY / ANTHROPIC_API_KEY (optional),
# CLAUDE_CODE_OAUTH_TOKEN (optional). Ollama running locally if you use ollama/* models.

bash harness/container/build.sh          # build localhost/secdevqa-eval (rootless podman)
```

### Bare LLM (no context)
```bash
$PY -m harness answer --model openai/gpt-5.4-mini --condition no_context
```

### Built-in agent (host, in-process tools)
```bash
$PY -m harness agent --model openai/gpt-5.4-mini            # full snapshot
$PY -m harness agent --model openai/gpt-5.4 --without advisory   # leave-one-out
$PY -m harness agent --model openai/gpt-5.4 --only advisory      # single-artifact
```

### Containerized off-the-shelf agent (recommended)
```bash
# One item, subscription auth, keep the sandbox for inspection:
$PY -m harness container --agent claude-code \
    --only-id psf/requests/issue/7209#1 --include-unapproved \
    --auth mount --keep-sandbox

# Whole benchmark (or a slice), selective provision, custom timeout:
$PY -m harness container --agent claude-code --limit 20 --auth mount
$PY -m harness container --agent claude-code --groups code,advisory   # RQ3
$PY -m harness container --agent claude-code --web                    # +web (open internet)
```
Flags: `--agent`, `--image`, `--groups`, `--web`, `--limit`, `--include-unapproved`,
`--timeout` (seconds/item, default 900), `--keep-sandbox`, `--only-id`, `--run-name`
(reuse to resume), `--auth {auto,env,mount}`.

**Watching a run:** the process console streams the container's live activity —
```
[1/1] psf/requests/issue/7209#1 ...
    │ [entrypoint] egress allowlist installed
    │ claude session init (model=claude-opus-4-8)
    │ → search_issues {"query": "trailing dot FQDN redirect"}
    │ → Read {"file_path": "/workspace/snapshot/repo/src/requests/sessions.py", …}
    │ final: success (16 turns, 97449ms)
    → ok (99s, 15 tool calls, 4394 chars)
```
The per-item structured tool events are also in `transcripts/<run>/<qid>.live.jsonl` (the UI's
live timeline).

### Grade
```bash
$PY -m harness grade \
    --answers harness/output/answers_<run>.jsonl \
    --judge ollama/gemma4:31b        # judge MUST differ from the candidate
```
Grading is **condition-aware**: internal facts (fix PRs/commits, fixed versions) are never scored
as no-context misses, and `container_*` / `snapshot_agent*` / `external_*` count as with-context.
Output: `grades_<run>__judge-<slug>.jsonl` + a summary by knowledge_type × outcome.

### Web UI
```bash
$PY -m harness ui                    # http://localhost:8766
```
- **Monitor** — launch runs (system / model / artifact groups / judge / egress) and watch them
  live (process log + per-item tool timeline).
- **Compare** — predictions across runs side by side, with gradings and gold answers.

To rebuild the front end after editing `ui/src`: `cd harness/ui && npm install && npm run build`
(`dist/` is gitignored). For live dev: `npm run dev` (proxies the API to `:8766`).

---

## 8. Directory layout of outputs

```
harness/output/
  answers_<run>.jsonl               one record per item (qid, response, condition, model,
                                    tool_calls_by_group, snapshot meta, runtime_secs)
  answers_<run>.launch.json         the UI launch parameters (used by "resume")
  grades_<run>__judge-<slug>.jsonl  per-item grading
  transcripts/<run>/<qid>.json      full trajectory / raw container output
  transcripts/<run>/<qid>.live.jsonl  live tool events (tailed by /api/live during a run)
  logs/<proc>.log                   subprocess console log (tailed by /api/procs)

harness/cache/
  repos/<owner>__<repo>/            blobless clone (shared across runs)
  worktrees/<owner>__<repo>/<sha>/  checked-out worktree at a commit (built-in agent)
  advisories/, vuln/                advisory index + resolved-id cache
  container/<run>/<qid>/            per-item container payload (removed unless --keep-sandbox)
```

---

## 9. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `401 Invalid bearer token` from claude | Bad/expired credential. Use `--auth mount`, or put a valid `sk-ant-oat01-…` token (from `claude setup-token`) in `.env`. |
| Container run finishes in ~4s, tiny answer | Auth failed before the agent ran — check the streamed console for the error. |
| `podman image exists` false / system shows "not installed" | Build the image: `bash harness/container/build.sh`. |
| `ipset … Operation not permitted` | Container missing caps — the runner passes `--cap-add NET_ADMIN,NET_RAW`; only an issue if you invoke podman by hand. |
| Model calls blocked | The provider domain isn't in the egress allowlist — add it in the UI or `harness/resources/egress.json`. Ollama needs `allow_ollama` + host-loopback networking. |
| Nothing streams to the console | Fixed — the runner streams the container output live; ensure you're on the current `container/run.py`. |
| A run seems stuck | Each item is killed at `--timeout` (default 900s) by a watchdog; lower it for smoke tests. |

---

## 10. Extending

- **Another off-the-shelf agent (e.g. opencode):** add an entry to `AGENT_ARGV` in
  `container/run.py` (build its headless argv + a stream parser) and to the launcher's system
  list. The MCP server, materializer, egress, and auth are agent-agnostic.
- **Built-in agent over MCP (in-container):** design captured in
  `container/TASK7_builtin_over_mcp.md` — run the LangChain agent as an MCP client via
  `langchain-mcp-adapters`, sharing the `stream_agent` loop.
- **New artifact group / tool:** add it to `ToolBox` + `TOOL_SCHEMAS` in `snapshot/tools.py`;
  it flows to the built-in agent and the MCP server automatically.
```
