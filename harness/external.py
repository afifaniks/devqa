"""
SecDevQA harness — external agent adapter (Claude Code, OpenCode, ...).

Runs an off-the-shelf coding agent headlessly inside a TIME-CAPPED SANDBOX directory
materialized per item:

  sandbox/
    repo/                  repository tree exported at the commit before the report
                           (git archive — no .git, so no access to post-report history)
    data/issues.jsonl      issue corpus <= report time, source thread excluded
    data/prs.jsonl         pull requests <= report time
    data/advisories.json   GHSA advisories published <= report time
    data/commit_log.txt    commit log up to the snapshot commit (most recent first)
    QUESTION.md            the question + ground rules

The agent's stdout is captured as its answer; stderr and run metadata go to the
transcript file. Records use the same schema as answer.py/agent.py with condition
`external_<agent>` (a with-context condition for grading).

LIMITATION (report in threats-to-validity): an external agent with shell access cannot
be *provably* time-capped — it could reach the live web. The prompt forbids it and the
sandbox contains no .git, but this condition is best-effort capped; the built-in typed-
tool agent (harness/agent.py) is the airtight one.

Usage:
  python -m harness external --agent claude-code --limit 1 --include-unapproved
  python -m harness external --agent opencode --model anthropic/claude-sonnet-4-6
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from harness.answer import iter_items, slugify
from harness.llm import load_jsonl, load_benchmark
from harness.snapshot import build_snapshot

ROOT = Path(__file__).parent.parent
DEFAULT_INPUT = ROOT / "dataset" / "security_benchmark_final.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "harness" / "output"
SANDBOX_ROOT = ROOT / "harness" / "cache" / "sandbox"

# Command templates. {prompt} is replaced; extra args appended from --agent-args.
# Both run with cwd = the sandbox directory.
AGENTS = {
    "claude-code": {
        "cmd": ["claude", "-p", "{prompt}", "--dangerously-skip-permissions"],
        "model_flag": "--model",
    },
    "opencode": {
        "cmd": ["opencode", "run", "{prompt}"],
        "model_flag": "--model",
    },
}

QUESTION_TMPL = """\
# Developer security question — {repo}

Today's date is {report_date}. You are answering as of this date: this directory is a
frozen snapshot of everything that exists today, and NOTHING AFTER THIS DATE EXISTS.

Available in this directory:
- `repo/` — the project source tree as of today
- `data/issues.jsonl` — the project's issue tracker up to today (one JSON per line)
- `data/prs.jsonl` — pull requests up to today
- `data/advisories.json` — GitHub security advisories for this project published up to today
- `data/commit_log.txt` — commit history up to today (most recent first)

GROUND RULES: Use ONLY the files in this directory. Do NOT access the internet, package
registries, or any external service — information from after today would invalidate
your answer. Do not modify any files.

Investigate (search the issues for duplicates or related reports, check the advisories,
read the relevant code), then print your final answer to the question below. Be direct
and specific; cite concrete identifiers (CVE/GHSA ids, versions, commits, issue/PR
numbers) only when you verified them here or are confident from general knowledge;
acknowledge uncertainty rather than guess.

## Question

{question}
"""


def materialize_sandbox(thread_id: str, qid: str, run_name: str) -> tuple[Path, dict]:
    """Build the per-item sandbox; returns (sandbox_dir, snapshot_meta)."""
    snap = build_snapshot(thread_id, {"code", "commits", "issues", "prs", "advisory"})
    dest = SANDBOX_ROOT / run_name / qid.replace("/", "__")
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "data").mkdir(parents=True)

    # repo/ — git archive of the snapshot commit: a plain tree, no .git.
    repo_dir = dest / "repo"
    repo_dir.mkdir()
    archive = subprocess.run(
        ["git", "archive", snap.commit_sha], cwd=snap.clone,
        capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", str(repo_dir)], input=archive.stdout,
                   check=True)

    log = subprocess.run(
        ["git", "log", "--max-count=2000", "--date=iso",
         "--pretty=format:%h %ad %an %s", snap.commit_sha],
        cwd=snap.clone, capture_output=True, text=True, check=True).stdout
    (dest / "data" / "commit_log.txt").write_text(log, encoding="utf-8")

    with open(dest / "data" / "issues.jsonl", "w", encoding="utf-8") as fh:
        for issue in snap.issues:
            fh.write(json.dumps(issue, ensure_ascii=False) + "\n")
    with open(dest / "data" / "prs.jsonl", "w", encoding="utf-8") as fh:
        for pr in snap.prs:
            fh.write(json.dumps(pr, ensure_ascii=False) + "\n")
    (dest / "data" / "advisories.json").write_text(
        json.dumps(snap.advisories, ensure_ascii=False, indent=1), encoding="utf-8")

    meta = {"commit": snap.commit_sha, "report_time": snap.report_time,
            "n_issues": len(snap.issues), "n_prs": len(snap.prs),
            "n_advisories": len(snap.advisories)}
    return dest, meta


def run_external(agent: str, model: str | None, sandbox: Path, prompt: str,
                 timeout: int, agent_args: list[str]) -> tuple[str, str, int, float]:
    """Run the agent CLI; returns (stdout, stderr, returncode, seconds)."""
    spec = AGENTS[agent]
    cmd = [a.replace("{prompt}", prompt) for a in spec["cmd"]]
    if model:
        cmd += [spec["model_flag"], model]
    cmd += agent_args
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=sandbox, capture_output=True, text=True,
                           timeout=timeout)
        return r.stdout.strip(), r.stderr, r.returncode, time.time() - t0
    except subprocess.TimeoutExpired as exc:
        return ((exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes)
                else (exc.stdout or "")), f"TIMEOUT after {timeout}s", -1, time.time() - t0


def run(input_path: Path, output_dir: Path, agent: str, model: str | None,
        force: bool, limit: int | None, include_unapproved: bool,
        timeout: int, keep_sandbox: bool, agent_args: list[str]) -> None:
    if shutil.which(AGENTS[agent]["cmd"][0]) is None:
        raise SystemExit(f"'{AGENTS[agent]['cmd'][0]}' not found on PATH — install "
                         f"{agent} first")
    threads = load_benchmark(input_path)
    items = iter_items(threads, include_unapproved)
    if limit:
        items = items[:limit]
    if not items:
        raise SystemExit(f"No eval items found in {input_path}.")

    condition = f"external_{agent.replace('-', '_')}"
    run_name = f"{slugify(model) + '_' if model else ''}{condition}"
    output_path = output_dir / f"answers_{run_name}.jsonl"
    transcripts_dir = output_dir / "transcripts" / run_name
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    done: set[str] = set()
    if output_path.exists() and not force:
        done = {r["qid"] for r in load_jsonl(output_path) if not r.get("error")}
        print(f"Resuming: {len(done)} answers already in {output_path}")

    print(f"Agent: {agent} | model: {model or '(agent default)'} "
          f"| condition: {condition} | items: {len(items)}")
    n_new = n_err = 0
    with open(output_path, "w" if force else "a", encoding="utf-8") as fh:
        for i, (thread, pair) in enumerate(items):
            qid = pair["qid"]
            if qid in done:
                continue
            print(f"[{i+1}/{len(items)}] {qid} ...", end=" ", flush=True)
            rec = {
                "qid": qid, "thread_id": thread["thread_id"],
                "repo": thread.get("repo"), "url": thread.get("url"),
                "condition": condition, "model": model or agent,
                "agent": agent,
                "knowledge_type": pair.get("knowledge_type"),
                "question": pair["question"],
                "answered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            sandbox = None
            try:
                sandbox, snap_meta = materialize_sandbox(
                    thread["thread_id"], qid, run_name)
                prompt = QUESTION_TMPL.format(
                    repo=thread.get("repo"), report_date=snap_meta["report_time"][:10],
                    question=pair["question"])
                stdout, stderr, rc, secs = run_external(
                    agent, model, sandbox, prompt, timeout, agent_args)
                if rc != 0 or not stdout:
                    raise RuntimeError(f"agent exit={rc}: {(stderr or stdout)[:300]}")
                rec.update({"response": stdout, "snapshot": snap_meta,
                            "runtime_secs": round(secs, 1)})
                (transcripts_dir / f"{qid.replace('/', '__')}.json").write_text(
                    json.dumps({"qid": qid, "agent": agent, "model": model,
                                "condition": condition, "snapshot": snap_meta,
                                "returncode": rc, "runtime_secs": round(secs, 1),
                                "stderr": stderr[-8000:],
                                "stdout": stdout[:20000]}, ensure_ascii=False, indent=1))
                n_new += 1
                print(f"ok ({secs:.0f}s, {len(stdout)} chars)")
            except Exception as exc:
                rec["error"] = str(exc)
                n_err += 1
                print(f"ERROR: {exc}")
            finally:
                if sandbox and not keep_sandbox:
                    shutil.rmtree(sandbox, ignore_errors=True)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()

    print(f"\nDone: {n_new} new answers, {len(done)} skipped, {n_err} errors")
    print(f"Output: {output_path}")
    print(f"Next: python -m harness grade --answers {output_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="External agent condition (sandboxed CLI agents).")
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    ap.add_argument("--agent", required=True, choices=sorted(AGENTS))
    ap.add_argument("--model", default=None,
                    help="model passthrough to the agent CLI (optional)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--include-unapproved", action="store_true")
    ap.add_argument("--timeout", type=int, default=600, help="seconds per item")
    ap.add_argument("--keep-sandbox", action="store_true",
                    help="keep per-item sandbox dirs for inspection")
    ap.add_argument("--agent-args", default="",
                    help="extra args appended to the agent command (space-separated)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    run(args.input, args.output_dir, args.agent, args.model, args.force, args.limit,
        args.include_unapproved, args.timeout, args.keep_sandbox,
        args.agent_args.split() if args.agent_args else [])


if __name__ == "__main__":
    main()
