"""
SecDevQA — Stage 2 (agent): the snapshot_agent condition.

The model under test answers each eval question with autonomous tool access over a
TIME-CAPPED snapshot (harness/snapshot.py): the repository checked out at the last commit
before the report, the issue/PR corpus up to the report time (source thread excluded),
and the GHSA advisory snapshot up to the report time. No live web.

Selective artifact provision (RQ3) is driven by tool-group gating:
  --without advisory            leave-one-out: full snapshot minus one group
  --only code                   single-artifact: one group alone
  (groups: code, commits, issues, prs, advisory)

Every tool call is recorded; transcripts land in
harness/output/transcripts/<run-name>/<qid>.json. Answers are written in the same record
format as harness/answer.py, with `condition` set to e.g.
  snapshot_agent | snapshot_agent-no_advisory | snapshot_agent-only_code
so grading stays condition-aware (any `snapshot_agent*` / `agent*` condition counts as a
with-context condition in harness/grade.py).

Usage:
  python -m harness agent --model openai/gpt-5.4-mini --limit 1 --include-unapproved
  python -m harness agent --model anthropic/claude-sonnet-4-6
  python -m harness agent --model openai/gpt-5.4 --without advisory
  python -m harness agent --model openai/gpt-5.4 --only advisory
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from harness.core.benchmark import default_benchmark, load_benchmark
from harness.core.paths import OUTPUT_DIR
from harness.core.runs import (acquire_run_lock, iter_items, make_run_name,
                               resume_state, select_items, slugify)
from harness.snapshot import build_snapshot
from harness.snapshot.stream_agent import file_emitter, run_streaming_agent
from harness.snapshot.tools import ALL_GROUPS, ToolBox

load_dotenv()

DEFAULT_INPUT = default_benchmark()
DEFAULT_OUTPUT_DIR = OUTPUT_DIR

SYSTEM_PROMPT = """\
You are a security-knowledgeable assistant answering a developer's question about the \
open-source project `{repo}`. Today's date is {report_date}.

You have tools over a snapshot of the project frozen at this date: the repository \
working tree{commit_note}, the issue tracker and pull requests as they existed today, \
and the GitHub security advisory database published up to today. {web_note}

Investigate before answering: search the tracker for duplicate or related reports, \
check the advisory database, and read the relevant code or history where useful. Then \
give a direct, specific answer to the developer. Cite concrete identifiers \
(CVE/GHSA ids, versions, commits, issue/PR numbers) only when you verified them with \
your tools or are confident from general knowledge; acknowledge uncertainty rather \
than guess. If the question cannot be resolved from the information available today, \
say so and give your best assessment. No generic padding."""


NO_WEB_NOTE = ("There is no live internet access, and nothing after this date exists.")
WEB_NOTE = (
    "You have access to the internet with web_search and web_fetch tools."
    "You can look into the internet for latest information. But make sure"
    "to note when your decision is based on information from the internet, and not from the snapshot.")


def condition_name(groups: set[str], web: bool = False) -> str:
    """Filesystem-safe condition name encoding the active artifact groups. A `+web`
    suffix marks runs that were also given live-internet tools (off-snapshot)."""
    missing = set(ALL_GROUPS) - groups
    if not missing:
        base = "snapshot_agent"
    elif len(groups) == 1:
        base = f"snapshot_agent-only_{next(iter(groups))}"
    elif len(missing) == 1:
        base = f"snapshot_agent-no_{next(iter(missing))}"
    else:
        base = "snapshot_agent-groups_" + "+".join(sorted(groups))
    return base + "+web" if web else base


def system_prompt_for(box: ToolBox) -> str:
    """The investigation system prompt, filled in for this snapshot."""
    commit_note = (f" (checked out at commit {box.snap.commit_sha[:12]})"
                   if box.snap.commit_sha else "")
    return SYSTEM_PROMPT.format(repo=box.snap.repo,
                                report_date=box.snap.report_time[:10],
                                commit_note=commit_note,
                                web_note=WEB_NOTE if box.web else NO_WEB_NOTE)


def run(input_path: Path, output_dir: Path, model: str, groups: set[str],
        condition: str, limit: int | None, include_unapproved: bool,
        max_steps: int, only_id: str | None = None,
        run_name: str | None = None, web: bool = False) -> None:
    threads = load_benchmark(input_path)
    items = select_items(iter_items(threads, include_unapproved), only_id)
    if limit:
        items = items[:limit]
    if not items:
        raise SystemExit(f"No eval items found in {input_path}.")

    run_name = make_run_name(f"{slugify(model)}_{condition}", only_id, run_name)
    output_path = output_dir / f"answers_{run_name}.jsonl"
    transcripts_dir = output_dir / "transcripts" / run_name
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    _lock = acquire_run_lock(output_path)  # noqa: F841 — held for process lifetime
    good, done = resume_state(output_path)
    if done:
        print(f"Resuming {run_name}: {len(done)} already done, "
              f"{len(items) - len(done)} remaining")

    print(f"Model: {model} | condition: {condition} | groups: {sorted(groups)} "
          f"| run: {run_name} | items: {len(items)}")
    n_new = n_err = 0
    with open(output_path, "w", encoding="utf-8") as fh:
        for r in good:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        fh.flush()
        for i, (thread, pair) in enumerate(items):
            qid = pair["qid"]
            if qid in done:
                continue
            print(f"[{i+1}/{len(items)}] {qid} ...", end=" ", flush=True)
            rec = {
                "qid": qid, "thread_id": thread["thread_id"],
                "repo": thread.get("repo"), "url": thread.get("url"),
                "condition": condition, "model": model,
                "knowledge_type": pair.get("knowledge_type"),
                "question": pair["question"],
                "answered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            try:
                snap = build_snapshot(thread["thread_id"], groups)
                box = ToolBox(snap, groups, web=web)
                # Live event sink: the streaming layer appends token/tool events here as
                # they happen, so the monitor UI can tail the in-flight item. The final
                # trajectory transcript (below) is still written in the canonical format.
                live_path = transcripts_dir / f"{qid.replace('/', '__')}.live.jsonl"
                emit = file_emitter(live_path)
                try:
                    text, transcript = run_streaming_agent(
                        model, pair["question"], box, system_prompt_for(box),
                        max_steps, emit)
                finally:
                    getattr(emit, "_fh").close()
                rec.update({
                    "response": text,
                    "snapshot": {"commit": snap.commit_sha,
                                 "report_time": snap.report_time,
                                 "n_issues": len(snap.issues),
                                 "n_prs": len(snap.prs),
                                 "n_advisories": len(snap.advisories)},
                    "tool_calls_by_group": _count_groups(box.calls),
                    "n_tool_calls": len(box.calls),
                })
                tpath = transcripts_dir / f"{qid.replace('/', '__')}.json"
                tpath.write_text(json.dumps(
                    {"qid": qid, "model": model, "condition": condition,
                     "snapshot_commit": snap.commit_sha,
                     "report_time": snap.report_time, "transcript": transcript},
                    ensure_ascii=False, indent=1))
                n_new += 1
                flag = "  ⚠ EMPTY response" if not text.strip() else ""
                print(f"ok ({len(box.calls)} tool calls, {len(text)} chars){flag}")
            except Exception as exc:
                rec["error"] = str(exc)
                n_err += 1
                print(f"ERROR: {exc}")
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            if i < len(items) - 1:
                time.sleep(0.3)

    print(f"\nDone: {n_new} answers, {n_err} errors")
    print(f"Output: {output_path}\nTranscripts: {transcripts_dir}")
    print(f"Next: python -m harness grade --answers {output_path}")


def _count_groups(calls: list[dict]) -> dict:
    out: dict[str, int] = {}
    for c in calls:
        if c.get("group"):
            out[c["group"]] = out.get(c["group"], 0) + 1
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="snapshot_agent condition (time-capped tools).")
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    ap.add_argument("--model", required=True, help="LiteLLM model id (must support tool calling)")
    ap.add_argument("--without", default="",
                    help="comma list of groups to remove (LOO), e.g. advisory")
    ap.add_argument("--only", default=None, choices=ALL_GROUPS,
                    help="single-artifact condition: enable one group only")
    ap.add_argument("--groups", default="",
                    help="explicit comma list of groups to enable (overrides --without/--only)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--include-unapproved", action="store_true")
    ap.add_argument("--max-steps", type=int, default=25,
                    help="max tool-calling rounds before a forced final answer")
    ap.add_argument("--web-search", action="store_true",
                    help="also give the agent live-internet web_search/web_fetch tools "
                         "(off-snapshot; adds a +web condition suffix)")
    ap.add_argument("--only-id", default=None,
                    help="Run a single benchmark instance by qid or thread_id")
    ap.add_argument("--run-name", default=None,
                    help="Explicit run name (default: model_condition[_instance]_timestamp)")
    args = ap.parse_args()

    without = {g.strip() for g in args.without.split(",") if g.strip()}
    explicit = {g.strip() for g in args.groups.split(",") if g.strip()}
    bad = (without | explicit) - set(ALL_GROUPS)
    if bad:
        raise SystemExit(f"unknown groups: {bad}; valid: {ALL_GROUPS}")
    if args.only and without:
        raise SystemExit("--only and --without are mutually exclusive")
    if explicit:
        groups = explicit
    elif args.only:
        groups = {args.only}
    else:
        groups = set(ALL_GROUPS) - without
    if not groups:
        raise SystemExit("at least one artifact group must be enabled")

    run(args.input, args.output_dir, args.model, groups,
        condition_name(groups, args.web_search), args.limit,
        args.include_unapproved, args.max_steps, args.only_id, args.run_name,
        web=args.web_search)


if __name__ == "__main__":
    main()
