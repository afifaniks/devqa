# Task 7 — Built-in agent over MCP (in container)

**Status:** deferred (design captured here; not yet implemented).
**Depends on:** Tasks 2–6 + 8 (all done: MCP server, materializer, image, egress, container runner,
external claude-code path — all validated end-to-end).

## Goal

Run the **built-in snapshot agent** through the *same* unified MCP interface and the *same*
egress-locked container as the external agents, so `snapshot_agent` and `container_claude_code`
differ only in the agent, not in how the snapshot is delivered. Today the built-in agent
(`harness/conditions/agent.py` → `harness/snapshot/stream_agent.py`) talks to `ToolBox`
**in-process on the host**; Task 7 moves it into the container as an **MCP client**.

Why bother (the built-in agent is already airtight on the host): uniformity (one execution path,
one image, one egress policy, one attribution source), and it lets the built-in agent run under
the exact same conditions we report for the external agents.

## Current pieces to reuse

- `harness/snapshot/stream_agent.py` — LangChain `create_agent` ReAct loop, `emit`-based live
  events (`token` / `tool_call` / `tool_result` / `final`), forced-final-after-budget. Currently
  builds tools by wrapping `ToolBox.execute` (`build_tools`).
- `harness/mcp/server.py` — the stdio MCP server (already used by claude-code). Same server,
  same `SECDEVQA_SNAPSHOT_DIR` / `SECDEVQA_LIVE_EVENTS` / `SECDEVQA_GROUPS` env contract.
- `langchain-mcp-adapters` (already installed in the image) — `load_mcp_tools()` turns an MCP
  session's tools into LangChain `StructuredTool`s that `create_agent` can consume directly.
- `harness/container/run.py` — the runner. `AGENT_ARGV` maps an agent name → the in-container
  argv; add a `"builtin"` entry. Auth/egress/materialize/mount plumbing is already generic.

## Design

Add an in-container driver `harness/container/builtin.py` (new), run as
`python -m harness.container.builtin --model <id> [--max-steps N]`:

1. Start an MCP client session against `python -m harness.mcp.server` (stdio), same env the
   claude `--mcp-config` uses. Use `langchain_mcp_adapters`:
   ```python
   from mcp import ClientSession, StdioServerParameters
   from mcp.client.stdio import stdio_client
   from langchain_mcp_adapters.tools import load_mcp_tools
   ```
2. `tools = await load_mcp_tools(session)` → feed straight into `create_agent(chat, tools=tools,
   system_prompt=...)`. Reuse `stream_agent._arun`'s event loop almost verbatim (it is already
   tool-source-agnostic — it keys off `on_tool_start/end` events, not `ToolBox`). Factor the
   agent loop in `stream_agent.py` so it accepts a ready list of LangChain tools instead of a
   `ToolBox`, and both host and container paths share it.
3. Model comes from `--model` (LiteLLM/LangChain id, e.g. `openai/gpt-5.4-mini`); the API key is
   an **env var** (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`), so the egress allowlist must include
   that provider — it already does. (Unlike claude-code, the built-in agent uses API models, not
   the claude subscription.)
4. Emit the final answer as the **last stdout line** as JSON: `{"final": "...",
   "tool_calls_by_group": {...}, "n_tool_calls": N}`. `run.py` parses this for the `builtin`
   agent (add a small branch alongside `_parse_stream_json`, or dispatch a per-agent parser).

### Runner changes (`run.py`)

- `AGENT_ARGV["builtin"] = _builtin_argv` where `_builtin_argv(prompt, web)` returns
  `["python3", "-m", "harness.container.builtin", "--model", MODEL, ...]` — **but** the prompt +
  model must reach it. Options: pass the question via a file in the payload (cleanest, avoids
  arg-length limits) or via `--question-file /workspace/snapshot/question.txt` written at
  materialize time. Add `model` as a runner arg (`--model`) that is required when
  `--agent builtin`.
- Add a per-agent result parser: `RESULT_PARSER = {"claude-code": _parse_stream_json,
  "builtin": _parse_builtin_json}`.
- The system prompt: reuse `harness/conditions/agent.py::SYSTEM_PROMPT` (repo/report_date/web
  notes) rather than the claude PROMPT_TMPL.

### Live events / attribution (decision to make)

The MCP server already logs `tool_call`/`tool_result` to `live.jsonl`. If `builtin.py` also emits
tool events (via `stream_agent`'s `emit`), tool calls get **double-counted**. Resolve one of:

- **(A) MCP server owns tool events; builtin emits only `token`/`step`/`final`.** Cleanest for
  attribution (single source), matches how claude-code works (MCP log = tool truth). Pass a flag
  to `builtin` to suppress tool events in its emitter. **Recommended.**
- (B) builtin owns all events; disable the MCP server's live logging when driven by builtin
  (e.g. omit `SECDEVQA_LIVE_EVENTS`). Loses the uniform "MCP log = attribution" story.

Go with (A): RQ4 attribution then comes from the MCP live log for **every** container agent,
identically.

## Files

- **new** `harness/container/builtin.py` — the in-container MCP-client agent driver.
- **edit** `harness/snapshot/stream_agent.py` — factor the agent loop to accept a tool list
  (share host + container); no behavior change on the host path.
- **edit** `harness/container/run.py` — `AGENT_ARGV["builtin"]`, `--model` arg, per-agent result
  parser, question-file materialization, `agent.py` system prompt for builtin.
- **edit** `harness/container/materialize.py` (maybe) — write `question.txt` into the payload.
- **edit** `harness/monitor/launcher.py` — add `container-builtin` to `/api/options` (needs_model
  = True, has_groups, has_web, has_egress) and to `_build_cmd` (pass `--model`).

## Testing

1. Unit: `load_mcp_tools` against a materialized payload on the host (outside a container) →
   confirm the 12 tools load as LangChain tools and one call round-trips.
2. In-container smoke: `python -m harness container --agent builtin --model openai/gpt-5.4-mini
   --only-id psf/requests/issue/7209#1 --include-unapproved --keep-sandbox` → expect a final
   answer, `tool_calls_by_group` populated from the MCP log, live events streamed.
3. Parity: compare `tool_calls_by_group` semantics with the host `snapshot_agent` run on the same
   item (should be the same tool vocabulary, same group gating under `--groups`).

## Gotchas

- **Model API key, not subscription:** builtin uses API models; ensure the key is in env and the
  provider domain is allowlisted (already is).
- **Event double-counting:** implement decision (A) above.
- **Async in the container:** `builtin.py` is async (MCP client is async); wrap in `asyncio.run`
  like `stream_agent.run_streaming_agent`.
- **`create_agent` with MCP tools:** MCP tool arg schemas come from the server; they should match
  `TOOL_SCHEMAS`, but verify `create_agent` doesn't inject extra middleware tools (the reason
  `stream_agent` uses `create_agent` not `create_deep_agent`).
- **Condition name:** `container_builtin` (grading already treats `container_*` as with-context).
