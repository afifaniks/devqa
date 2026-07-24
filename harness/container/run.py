"""
SecDevQA harness — containerized agent runner (unified MCP interface).

Runs an agent against one benchmark item inside a per-item podman container that provides the
SAME interface to every agent type:

  * the time-capped snapshot is materialized on the host (harness/container/materialize.py) and
    bind-mounted read-only at /workspace/snapshot;
  * an in-container MCP server (harness/mcp/server.py) exposes the artifact-grouped snapshot
    tools over stdio — this is the unified tool surface, identical to what the built-in agent
    uses, and every call is logged to /workspace/live.jsonl (streamed to the monitor UI);
  * egress is locked to the allowlist by the entrypoint firewall (harness/container/egress.py):
    the model API + vuln-resolution hosts only, so the time-cap holds even for a shell agent —
    unless the +web condition opts into open internet.

The claude-code agent additionally keeps its own file/shell tools over the checked-out repo;
the MCP server carries issues/PRs/advisories/commit-history, which are not on disk. The
built-in agent (--agent builtin) reaches the same MCP server via its LangChain client
(see harness/container/builtin.py).

Records match the answer.py schema with condition ``coding_agent_<agent>`` (a with-context
condition for grading). Auth is passed through from the host env: CLAUDE_CODE_OAUTH_TOKEN
(subscription) is preferred, else ANTHROPIC_API_KEY / OPENAI_API_KEY.

Usage:
  python -m harness coding-agent --agent claude-code --limit 1 --include-unapproved
  python -m harness coding-agent --agent claude-code --only-id psf/requests/issue/7209#1
  python -m harness coding-agent --agent claude-code --web        # +web (open internet)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from harness.container.egress import default_policy
from harness.container.materialize import materialize_payload
from harness.core.benchmark import default_benchmark, load_benchmark
from harness.core.paths import CACHE_DIR, HARNESS_DIR, OUTPUT_DIR
from harness.core.prompts import coding_agent_prompt
from harness.core.runs import (iter_items, make_run_name, resume_state,
                               select_items)
from harness.snapshot.tools import ALL_GROUPS, MAX_RESULT_CHARS

load_dotenv()

DEFAULT_INPUT = default_benchmark()
DEFAULT_IMAGE = os.environ.get("SECDEVQA_IMAGE", "localhost/secdevqa-eval:latest")
SANDBOX_ROOT = CACHE_DIR / "container"

# In-container paths (fixed by convention; the runner mounts onto these).
C_WORKSPACE = "/workspace"
C_SNAPSHOT = "/workspace/snapshot"
C_MIRROR = "/workspace/snapshot/repo.git"   # bare, ancestors-only (read-only mount)
C_REPO = "/workspace/repo"                  # the entrypoint's clone, checked out at base commit
C_LIVE = "/workspace/live.jsonl"
C_MCP_CONFIG = "/workspace/mcp.json"
C_HARNESS = "/opt/secdevqa/harness"
C_ENTRYPOINT = "/opt/secdevqa/harness/container/entrypoint.sh"

# Auth env vars forwarded into the container, in preference order (subscription first).
AUTH_ENV_VARS = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")

# ---------------------------------------------------------------------------
# MCP client config + agent command (per agent)
# ---------------------------------------------------------------------------

def _mcp_config(groups: set[str]) -> dict:
    """The stdio MCP server spec the in-container agent launches (client-spawned subprocess)."""
    return {
        "mcpServers": {
            "secdevqa": {
                "command": "python3",
                "args": ["-m", "harness.mcp.server"],
                "env": {
                    "SECDEVQA_SNAPSHOT_DIR": C_SNAPSHOT,
                    # The code tools operate on the entrypoint's real clone, not the payload.
                    "SECDEVQA_REPO_DIR": C_REPO,
                    "SECDEVQA_LIVE_EVENTS": C_LIVE,
                    "SECDEVQA_GROUPS": ",".join(sorted(groups)),
                },
            }
        }
    }


def _claude_argv(prompt: str, web: bool) -> list[str]:
    """The claude-code invocation (headless, stream-json). Keeps its own file tools; the MCP
    tools are namespaced mcp__secdevqa__*. Web tools are disabled unless the +web condition."""
    argv = [
        "claude", "-p", prompt,
        "--mcp-config", C_MCP_CONFIG,
        "--strict-mcp-config",          # ignore the host's global MCP servers (isolation)
        "--output-format", "stream-json", "--verbose",
        "--dangerously-skip-permissions",
    ]
    if not web:
        # variadic flag: pass tools as separate args, not a comma string.
        argv += ["--disallowedTools", "WebSearch", "WebFetch"]
    return argv


AGENT_ARGV = {"claude-code": _claude_argv}


# ---------------------------------------------------------------------------
# Container assembly
# ---------------------------------------------------------------------------

def resolve_auth(run_name: str, mode: str = "auto") -> tuple[dict[str, str], list[str]]:
    """Resolve agent credentials into (container env, extra mount flags).

    `mode`: "env" uses an env token only; "mount" mounts the host claude-code login only; "auto"
    prefers an env token (CLAUDE_CODE_OAUTH_TOKEN / ANTHROPIC_API_KEY / OPENAI_API_KEY) and falls
    back to the mounted login. The host login is kept untouched: the credentials are COPIED into a
    per-run dir and mounted from there, so a token refresh inside the container cannot clobber the
    host's credential file (safe for a run short enough not to trigger a refresh)."""
    if mode != "mount":
        env = {k: os.environ[k] for k in AUTH_ENV_VARS if os.environ.get(k)}
        if env:
            return env, []
        if mode == "env":
            raise SystemExit("--auth env: no CLAUDE_CODE_OAUTH_TOKEN / ANTHROPIC_API_KEY set.")

    cred = Path.home() / ".claude" / ".credentials.json"
    if not cred.exists():
        raise SystemExit(
            "No agent credentials found. Set CLAUDE_CODE_OAUTH_TOKEN (run `claude setup-token`) "
            "or ANTHROPIC_API_KEY, or log in with claude-code so ~/.claude/.credentials.json "
            "exists to mount.")

    home_copy = SANDBOX_ROOT / f"_auth_{run_name}"
    claude_dir = home_copy / ".claude"
    if home_copy.exists():
        shutil.rmtree(home_copy)
    claude_dir.mkdir(parents=True)
    shutil.copy2(cred, claude_dir / ".credentials.json")
    for extra in ("settings.json",):
        src = Path.home() / ".claude" / extra
        if src.exists():
            shutil.copy2(src, claude_dir / extra)
    account = Path.home() / ".claude.json"          # onboarding/account state (avoids prompts)
    mounts = ["-v", f"{claude_dir}:/root/.claude"]
    if account.exists():
        shutil.copy2(account, home_copy / ".claude.json")
        mounts += ["-v", f"{home_copy / '.claude.json'}:/root/.claude.json"]
    return {}, mounts


def _podman_cmd(image: str, payload_dir: Path, live_file: Path, mcp_file: Path,
                agent_argv: list[str], policy, auth_env: dict[str, str],
                auth_mounts: list[str], base_commit: str = "") -> list[str]:
    # IS_SANDBOX=1 lets claude-code accept --dangerously-skip-permissions as root (we need root
    # in-container for the egress firewall, and we genuinely are sandboxed).
    # SECDEVQA_REPO_* drive the entrypoint's clone-and-checkout of the base commit.
    repo_env = {"SECDEVQA_REPO_MIRROR": C_MIRROR, "SECDEVQA_REPO_DIR": C_REPO,
                "SECDEVQA_BASE_COMMIT": base_commit} if base_commit else {}
    env = {"IS_SANDBOX": "1", **repo_env, **policy.env(), **auth_env}
    env_flags: list[str] = []
    for k, v in env.items():
        env_flags += ["-e", f"{k}={v}"]
    return [
        "podman", "run", "--rm",
        "-v", f"{payload_dir}:{C_SNAPSHOT}:ro",
        "-v", f"{live_file}:{C_LIVE}",
        "-v", f"{mcp_file}:{C_MCP_CONFIG}:ro",
        "-v", f"{HARNESS_DIR}:{C_HARNESS}:ro",
        *auth_mounts,
        "-w", C_WORKSPACE,
        *policy.podman_args(),
        *env_flags,
        image,
        "bash", C_ENTRYPOINT, *agent_argv,
    ]


# ---------------------------------------------------------------------------
# stream-json parsing (final answer + the agent's own native tool calls)
# ---------------------------------------------------------------------------

_NATIVE_TOOL_GROUP = {"Read": "code", "Grep": "code", "Glob": "code",
                      "LS": "code", "Bash": "code"}


def _read_live(live_file: Path) -> list[dict]:
    """Parse the live-events file, skipping any half-written trailing line (the container
    appends to it while we may already be reading)."""
    events: list[dict] = []
    try:
        text = live_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return events
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _cap(s: str, n: int = MAX_RESULT_CHARS) -> str:
    """Bound a captured tool output the same way ToolBox bounds its own results."""
    return s if len(s) <= n else s[:n] + f"\n... [truncated, {len(s)} chars total]"


def _tool_result_text(content) -> str:
    """Flatten a stream-json tool_result `content` (str, or a list of content blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                parts.append(b.get("text") or b.get("content") or json.dumps(b, ensure_ascii=False))
            else:
                parts.append(str(b))
        return "\n".join(p for p in parts if p)
    return "" if content is None else json.dumps(content, ensure_ascii=False)


def _parse_stream_json(stdout: str) -> tuple[str, list[dict]]:
    """Return (final_answer, native_tool_calls). MCP tool calls (mcp__*) are logged by the MCP
    server itself, so only the agent's OWN tools are collected here — that recovers the code
    attribution the MCP log cannot see (the agent reads the repo with its own file tools).

    Each native call carries its `result`: the agent's own file/shell tools bypass the MCP
    server, so this stream is the ONLY place their output can be captured."""
    final = ""
    native: list[dict] = []
    by_use_id: dict[str, dict] = {}
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = ev.get("type")
        if kind == "result" and ev.get("result"):
            final = ev["result"]
        elif kind in ("assistant", "user"):
            for block in (ev.get("message", {}) or {}).get("content", []) or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    name = block.get("name", "")
                    if name.startswith("mcp__"):
                        continue
                    call = {"tool": name, "group": _NATIVE_TOOL_GROUP.get(name),
                            "args": block.get("input"), "result": ""}
                    native.append(call)
                    if block.get("id"):
                        by_use_id[block["id"]] = call
                elif block.get("type") == "tool_result":
                    call = by_use_id.get(block.get("tool_use_id"))
                    if call is not None:
                        call["result"] = _cap(_tool_result_text(block.get("content")))
    return final, native


def _humanize_container_line(line: str) -> str | None:
    """Turn one raw container output line into a concise console line, or None to drop it.

    Non-JSON lines (the entrypoint firewall log, claude's own diagnostics) pass through verbatim
    — that is the "what's happening in the container" the process console should show. stream-json
    events are summarized: session init, each tool call, and the final result."""
    s = line.rstrip("\n")
    if not s.strip():
        return None
    if not s.lstrip().startswith("{"):
        text = s.strip()                       # entrypoint/firewall/agent stderr — show as-is
        return text if len(text) <= 240 else text[:240] + " …"
    try:
        ev = json.loads(s)
    except json.JSONDecodeError:
        return s.strip()
    kind = ev.get("type")
    if kind == "system" and ev.get("subtype") == "init":
        return f"claude session init (model={ev.get('model', '?')})"
    if kind == "assistant":
        calls = []
        for b in (ev.get("message", {}) or {}).get("content", []) or []:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                name = (b.get("name") or "").replace("mcp__secdevqa__", "")
                args = json.dumps(b.get("input") or {}, ensure_ascii=False)
                calls.append(f"→ {name} {args[:80]}")
        return "  ".join(calls) if calls else None
    if kind == "result":
        return (f"final: {ev.get('subtype', '?')} "
                f"({ev.get('num_turns', '?')} turns, {ev.get('duration_ms', '?')}ms)")
    return None


def _stream_container(cmd: list[str], timeout: int) -> tuple[str, int, float, bool]:
    """Run the container, echoing a readable summary of its activity to stdout as it happens (so
    it shows live in the process console), while accumulating the full output for answer parsing.
    Returns (full_output, returncode, seconds, timed_out)."""
    import threading
    t0 = time.time()
    # errors="replace": the merged container stream can carry non-UTF-8 bytes (a git patch or
    # binary file echoed by the agent's Bash/Read tools); strict decoding would crash the run.
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", bufsize=1)
    timed_out = {"v": False}

    def _kill() -> None:
        timed_out["v"] = True
        proc.kill()

    timer = threading.Timer(timeout, _kill)
    timer.start()
    lines: list[str] = []
    try:
        for line in proc.stdout:            # type: ignore[union-attr]
            lines.append(line)
            summary = _humanize_container_line(line)
            if summary:
                print(f"    │ {summary}", flush=True)
    finally:
        proc.wait()
        timer.cancel()
    return "".join(lines), proc.returncode, time.time() - t0, timed_out["v"]


def _append_native_tools_to_live(live_file: Path, native: list[dict]) -> None:
    """Fold the agent's own tool calls AND their outputs into the live-events file, so the
    live file is a complete record of every tool the agent used — MCP and native alike —
    for the UI timeline, RQ4 attribution, and transcript assembly."""
    if not native:
        return
    with open(live_file, "a", encoding="utf-8") as fh:
        for i, c in enumerate(native, 1):
            step = f"native-{i}"
            fh.write(json.dumps({"t": "tool_call", "step": step,
                                 "tool": c["tool"], "group": c["group"],
                                 "args": c["args"]}, ensure_ascii=False) + "\n")
            result = c.get("result") or ""
            fh.write(json.dumps({"t": "tool_result", "step": step,
                                 "tool": c["tool"], "group": c["group"],
                                 "chars": len(result), "result": result},
                                ensure_ascii=False) + "\n")


def _transcript_from_live(live_file: Path) -> list[dict]:
    """Build the final transcript from the live-events file.

    Emits the SAME step schema the in-process agent writes
    (``{step, type: "tool", tool, group, args, result}``) so the monitor UI renders
    coding-agent and snapshot_agent transcripts through one code path."""
    steps: dict = {}
    out: list[dict] = []
    for ev in _read_live(live_file):
        step = ev.get("step")
        if ev.get("t") == "tool_call":
            entry = {"step": step, "type": "tool", "tool": ev.get("tool"),
                     "group": ev.get("group"), "args": ev.get("args"), "result": ""}
            out.append(entry)
            steps[step] = entry
        elif ev.get("t") == "tool_result":
            entry = steps.get(step)
            if entry is not None:
                entry["result"] = ev.get("result") or ""
    return out


# ---------------------------------------------------------------------------
# One item
# ---------------------------------------------------------------------------

def _run_item(thread: dict, pair: dict, agent: str, image: str, groups: set[str],
              web: bool, timeout: int, transcripts_dir: Path, keep_sandbox: bool,
              auth_env: dict[str, str], auth_mounts: list[str]) -> dict:
    qid = pair["qid"]
    thread_id = thread["thread_id"]
    slug = qid.replace("/", "__")
    payload_dir = SANDBOX_ROOT / transcripts_dir.name / slug
    live_file = transcripts_dir / f"{slug}.live.jsonl"
    mcp_file = payload_dir.parent / f"{slug}.mcp.json"

    rec = {
        "qid": qid, "thread_id": thread_id,
        "repo": thread.get("repo"), "url": thread.get("url"),
        "condition": f"coding_agent_{agent.replace('-', '_')}",
        "model": agent, "agent": agent,
        "knowledge_type": pair.get("knowledge_type"),
        "question": pair["question"],
        "answered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    try:
        if payload_dir.exists():
            shutil.rmtree(payload_dir)
        meta = materialize_payload(thread_id, groups, payload_dir)
        live_file.parent.mkdir(parents=True, exist_ok=True)
        live_file.write_text("")                       # bind target must pre-exist
        mcp_file.write_text(json.dumps(_mcp_config(groups)), encoding="utf-8")

        prompt = coding_agent_prompt(
            repo=thread.get("repo"), report_date=meta["report_time"][:10],
            question=pair["question"], web=web)
        policy = default_policy(web=web)
        argv = AGENT_ARGV[agent](prompt, web)
        # Only ask the entrypoint to clone when a mirror was actually materialized: under an
        # RQ3 condition without the `code` group there is no repository to provide.
        base_commit = (meta.get("commit_sha") or "") if meta.get("has_repo") else ""
        cmd = _podman_cmd(image, payload_dir, live_file, mcp_file, argv, policy,
                          auth_env, auth_mounts, base_commit=base_commit)

        output, rc, secs, timed_out = _stream_container(cmd, timeout)
        if timed_out:
            raise subprocess.TimeoutExpired(cmd, timeout)

        final, native = _parse_stream_json(output)
        _append_native_tools_to_live(live_file, native)
        mcp_calls = _count_mcp_calls(live_file)

        if not final:
            raise RuntimeError(f"no final answer (rc={rc}): {output[-400:]}")

        rec.update({
            "response": final,
            "snapshot": {k: meta[k] for k in ("commit_sha", "report_time", "n_issues",
                                              "n_prs", "n_advisories")},
            "tool_calls_by_group": mcp_calls,
            "n_tool_calls": sum(mcp_calls.values()) + len(native),
            "n_native_tool_calls": len(native),
            "runtime_secs": round(secs, 1),
        })
        (transcripts_dir / f"{slug}.json").write_text(json.dumps(
            {"qid": qid, "agent": agent, "condition": rec["condition"],
             "model": agent, "report_time": meta.get("report_time"),
             "snapshot_commit": meta.get("commit_sha"),
             "snapshot": meta, "returncode": rc,
             "runtime_secs": round(secs, 1), "native_tools": native,
             # `transcript` is the key the monitor UI renders; same step schema as the
             # in-process agent, rebuilt from the live-events file (MCP + native calls).
             "transcript": _transcript_from_live(live_file),
             "output": output[-60000:]}, ensure_ascii=False, indent=1))
    except subprocess.TimeoutExpired:
        rec["error"] = f"TIMEOUT after {timeout}s"
    except Exception as exc:  # noqa: BLE001 — one item's failure must not kill the run
        rec["error"] = str(exc)
    finally:
        if not keep_sandbox and payload_dir.exists():
            shutil.rmtree(payload_dir, ignore_errors=True)
            mcp_file.unlink(missing_ok=True)
    return rec


def _count_mcp_calls(live_file: Path) -> dict[str, int]:
    """Per-group MCP tool-call counts from the live-events file (RQ4 attribution)."""
    out: dict[str, int] = {}
    for ev in _read_live(live_file):
        if ev.get("t") == "tool_call" and ev.get("group") and str(ev.get("step", "")).isdigit():
            out[ev["group"]] = out.get(ev["group"], 0) + 1
    return out


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def run(input_path: Path, agent: str, image: str, groups: set[str], web: bool,
        limit: int | None, include_unapproved: bool, timeout: int,
        keep_sandbox: bool, only_id: str | None, run_name: str | None,
        auth_mode: str = "auto") -> None:
    if agent not in AGENT_ARGV:
        raise SystemExit(f"unknown agent {agent!r}; supported: {sorted(AGENT_ARGV)}")
    if shutil.which("podman") is None:
        raise SystemExit("podman not found on PATH")

    threads = load_benchmark(input_path)
    items = select_items(iter_items(threads, include_unapproved), only_id)
    if limit:
        items = items[:limit]
    if not items:
        raise SystemExit(f"No eval items found in {input_path}.")

    condition = f"coding_agent_{agent.replace('-', '_')}" + ("+web" if web else "")
    run_name = make_run_name(condition, only_id, run_name)
    output_path = OUTPUT_DIR / f"answers_{run_name}.jsonl"
    transcripts_dir = OUTPUT_DIR / "transcripts" / run_name
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    good, done = resume_state(output_path)
    if done:
        print(f"Resuming {run_name}: {len(done)} done, {len(items) - len(done)} remaining")

    auth_env, auth_mounts = resolve_auth(run_name, auth_mode)
    print(f"Auth: {'env ' + '+'.join(auth_env) if auth_env else 'mounted ~/.claude credentials'}")
    print(f"Agent: {agent} | image: {image} | condition: {condition} | "
          f"groups: {sorted(groups)} | run: {run_name} | items: {len(items)}")
    n_new = n_err = 0
    with open(output_path, "w", encoding="utf-8") as fh:
        for r in good:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        fh.flush()
        for i, (thread, pair) in enumerate(items):
            if pair["qid"] in done:
                continue
            print(f"[{i+1}/{len(items)}] {pair['qid']} ...", flush=True)
            rec = _run_item(thread, pair, agent, image, groups, web, timeout,
                            transcripts_dir, keep_sandbox, auth_env, auth_mounts)
            if rec.get("error"):
                n_err += 1
                print(f"    → ERROR: {rec['error']}")
            else:
                n_new += 1
                print(f"    → ok ({rec['runtime_secs']:.0f}s, {rec['n_tool_calls']} tool calls, "
                      f"{len(rec['response'])} chars)")
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()

    # Credential hygiene: never leave the mounted-login copy on disk after the run.
    auth_copy = SANDBOX_ROOT / f"_auth_{run_name}"
    if auth_copy.exists():
        shutil.rmtree(auth_copy, ignore_errors=True)

    print(f"\nDone: {n_new} answers, {len(done)} kept, {n_err} errors")
    print(f"Output: {output_path}")
    print(f"Next: python -m harness grade --answers {output_path}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Off-the-shelf coding-agent condition (containerized, unified MCP).")
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--agent", required=True, choices=sorted(AGENT_ARGV))
    ap.add_argument("--image", default=DEFAULT_IMAGE)
    ap.add_argument("--groups", default="", help="comma list; default all artifact groups")
    ap.add_argument("--web", action="store_true",
                    help="+web: open internet in the container (breaks the time-cap)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--include-unapproved", action="store_true")
    ap.add_argument("--timeout", type=int, default=900, help="seconds per item")
    ap.add_argument("--keep-sandbox", action="store_true")
    ap.add_argument("--only-id", default=None)
    ap.add_argument("--run-name", default=None)
    ap.add_argument("--auth", choices=("auto", "env", "mount"), default="auto",
                    help="credential source: env token, mounted ~/.claude login, or auto")
    args = ap.parse_args()

    groups = ({g.strip() for g in args.groups.split(",") if g.strip()}
              if args.groups else set(ALL_GROUPS))
    bad = groups - set(ALL_GROUPS)
    if bad:
        raise SystemExit(f"unknown groups: {sorted(bad)}; valid: {ALL_GROUPS}")

    run(args.input, args.agent, args.image, groups, args.web, args.limit,
        args.include_unapproved, args.timeout, args.keep_sandbox,
        args.only_id, args.run_name, args.auth)


if __name__ == "__main__":
    main()
