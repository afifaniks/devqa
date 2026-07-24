"""
SecDevQA — streaming execution layer for the snapshot_agent condition.

The *evaluation business logic* lives in harness/agent.py: which items to run, building
the time-capped snapshot + ToolBox, naming conditions, and writing answer records and
trajectory transcripts. THIS module is the streaming layer only. It drives one question to
a final answer over a LangChain ReAct agent and emits token + tool events live as they
happen, while reconstructing the trajectory in exactly agent.py's existing transcript
format.

Why LangChain `create_agent` and not `deepagents.create_deep_agent`: create_deep_agent
unconditionally bundles planning (`write_todos`), filesystem (`ls`/`read_file`/...), and
sub-agent (`task`) middleware that inject extra tools into every run. Those would corrupt
the RQ4 tool-attribution counts (tool calls by artifact group) and the trajectory, which
must contain only our five typed snapshot groups. `create_agent` is the same LangChain
ReAct primitive deepagents wraps, with none of that middleware — so the agent sees exactly
the snapshot tools and nothing else.

Every tool the agent calls is routed through `ToolBox.execute`, so RQ4 counts
(`box.calls`) and the MAX_RESULT_CHARS truncation are unchanged from the non-streaming
path. No output-token cap is imposed for the same reason as agent.py: thinking models
spend their budget on a reasoning trace before answering (Anthropic, which requires a
max_tokens, is the one exception and gets a generous default).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Callable

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.errors import GraphRecursionError

from harness.snapshot.tools import TOOL_SCHEMAS, ALL_GROUPS, ToolBox

# An emit callback takes one event dict. A no-op default means callers that don't care
# about live events pay nothing.
Emit = Callable[[dict], None]


def _noop(_event: dict) -> None:
    pass


# ---------------------------------------------------------------------------
# Live event sink — one JSONL file per item, tailed by the monitor UI
# ---------------------------------------------------------------------------

def file_emitter(path: Path) -> Emit:
    """An emit callback that appends each event as one JSON line and flushes, so the
    monitor can tail the file while the item is still running. Truncates any stale file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = path.open("w", encoding="utf-8")

    def emit(event: dict) -> None:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        fh.flush()

    emit._fh = fh  # type: ignore[attr-defined]  # keep a handle so callers can close
    return emit


# ---------------------------------------------------------------------------
# Model + tools
# ---------------------------------------------------------------------------

def langchain_model(model: str):
    """Map our `provider/model` id onto a LangChain chat model that supports tool calling.
    Ollama is routed to ChatOllama (the chat endpoint — tool calling requires it, mirroring
    agent.py's ollama_chat routing). The original id is kept by the caller for records."""
    provider, _, name = model.partition("/")
    if provider == "ollama":
        from langchain_ollama import ChatOllama
        # num_predict left at the Ollama default (-1, unbounded) — no output-token cap.
        return ChatOllama(model=name)
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=name)
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        # Anthropic's API requires max_tokens; LangChain defaults it to 1024, too small for
        # agentic answers. Give it generous headroom (still a provider constraint, not our cap).
        return ChatAnthropic(model=name, max_tokens=8192)
    # Anything else: let LangChain resolve the provider from the prefix.
    from langchain.chat_models import init_chat_model
    return init_chat_model(name, model_provider=provider)


def build_tools(box: ToolBox) -> list[StructuredTool]:
    """One LangChain tool per active snapshot tool. Each routes through `box.execute`, so
    tool-call recording (RQ4) and result truncation stay identical to the non-streaming
    path; args schemas come straight from harness/tools.TOOL_SCHEMAS."""
    tools: list[StructuredTool] = []
    # The five artifact groups (gated by box.groups) plus the optional web group
    # (gated by box.web — off-snapshot, not part of ALL_GROUPS).
    active = [g for g in ALL_GROUPS if g in box.groups]
    if box.web:
        active.append("web")
    for group in active:
        for schema in TOOL_SCHEMAS[group]:
            spec = schema["function"]
            name = spec["name"]

            def runner(_tool=name, **kwargs) -> str:
                return box.execute(_tool, kwargs)

            tools.append(StructuredTool.from_function(
                func=runner, name=name, description=spec["description"],
                args_schema=spec["parameters"]))
    return tools


# ---------------------------------------------------------------------------
# Streaming agent run
# ---------------------------------------------------------------------------

async def _arun(model: str, question: str, box: ToolBox, system_prompt: str,
                max_steps: int, emit: Emit) -> tuple[str, list[dict]]:
    chat = langchain_model(model)
    tools = build_tools(box)
    agent = create_agent(chat, tools=tools, system_prompt=system_prompt)

    transcript: list[dict] = []
    # Mirror agent.py's conversation so a forced final after the step budget can be asked
    # without tools. Rebuilt from streamed events (the AI/tool messages as they arrive).
    convo = [SystemMessage(system_prompt), HumanMessage(question)]
    step = 0
    pending: dict[str, dict] = {}     # tool run_id -> {tool, group, args, step}
    final = ""

    emit({"t": "start", "question": question})
    # Each model turn + its tools is ~2 langgraph super-steps; +2 slack.
    config = {"recursion_limit": max_steps * 2 + 2}
    try:
        async for ev in agent.astream_events(
                {"messages": [("user", question)]}, version="v2", config=config):
            kind = ev["event"]
            if kind == "on_chat_model_start":
                step += 1
            elif kind == "on_chat_model_stream":
                chunk = ev["data"]["chunk"]
                text = _text_of(getattr(chunk, "content", ""))
                if text:
                    emit({"t": "token", "step": step, "text": text})
            elif kind == "on_chat_model_end":
                msg = ev["data"]["output"]
                convo.append(msg)
                if not getattr(msg, "tool_calls", None):
                    content = _text_of(getattr(msg, "content", "")) \
                        or _text_of(getattr(msg, "reasoning_content", "") or "")
                    if content:
                        final = content
            elif kind == "on_tool_start":
                tool = ev["name"]
                args = ev["data"].get("input") or {}
                pending[ev["run_id"]] = {
                    "tool": tool, "group": ToolBox.GROUP_OF_TOOL.get(tool),
                    "args": args, "step": step}
                emit({"t": "tool_call", "step": step, "tool": tool,
                      "group": ToolBox.GROUP_OF_TOOL.get(tool), "args": args})
            elif kind == "on_tool_end":
                info = pending.pop(ev["run_id"], {"tool": ev["name"],
                                                  "group": ToolBox.GROUP_OF_TOOL.get(ev["name"]),
                                                  "args": {}, "step": step})
                out = ev["data"]["output"]
                result = getattr(out, "content", None)
                result = result if isinstance(result, str) else str(out)
                convo.append(out)
                transcript.append({"step": info["step"], "type": "tool",
                                   "tool": info["tool"], "group": info["group"],
                                   "args": info["args"], "result": result})
                emit({"t": "tool_result", "step": info["step"], "tool": info["tool"],
                      "group": info["group"], "chars": len(result)})
        transcript.append({"step": step, "type": "final", "chars": len(final)})
        emit({"t": "final", "chars": len(final)})
    except GraphRecursionError:
        # Out of step budget — force a final answer without tools, mirroring agent.py.
        convo.append(HumanMessage("You are out of tool budget. Give your final answer now."))
        resp = await chat.ainvoke(convo)
        final = _text_of(getattr(resp, "content", "")) \
            or _text_of(getattr(resp, "reasoning_content", "") or "")
        transcript.append({"step": step + 1, "type": "final_forced", "chars": len(final)})
        emit({"t": "final_forced", "chars": len(final)})

    emit({"t": "done", "chars": len(final)})
    return final, transcript


def _text_of(content) -> str:
    """LangChain message content may be a string or a list of content blocks
    (e.g. [{'type':'text','text':...}, ...]); flatten to plain text."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts).strip()
    return ""


def run_streaming_agent(model: str, question: str, box: ToolBox, system_prompt: str,
                        max_steps: int, emit: Emit | None = None) -> tuple[str, list[dict]]:
    """Synchronous entry point used by harness/agent.py. Returns (final_answer,
    transcript) in agent.py's existing transcript format; streams live events to `emit`."""
    return asyncio.run(_arun(model, question, box, system_prompt, max_steps,
                             emit or _noop))
