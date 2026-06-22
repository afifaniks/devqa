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

import litellm
from dotenv import load_dotenv

from harness.answer import iter_items, slugify
from harness.llm import load_jsonl, load_benchmark
from harness.snapshot import build_snapshot
from harness.tools import ALL_GROUPS, ToolBox, schemas_for

load_dotenv()

ROOT = Path(__file__).parent.parent
DEFAULT_INPUT = ROOT / "dataset" / "security_benchmark_final.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "harness" / "output"

SYSTEM_PROMPT = """\
You are a security-knowledgeable assistant answering a developer's question about the \
open-source project `{repo}`. Today's date is {report_date}.

You have tools over a snapshot of the project frozen at this date: the repository \
working tree{commit_note}, the issue tracker and pull requests as they existed today, \
and the GitHub security advisory database published up to today. There is no live \
internet access, and nothing after this date exists.

Investigate before answering: search the tracker for duplicate or related reports, \
check the advisory database, and read the relevant code or history where useful. Then \
give a direct, specific answer to the developer. Cite concrete identifiers \
(CVE/GHSA ids, versions, commits, issue/PR numbers) only when you verified them with \
your tools or are confident from general knowledge; acknowledge uncertainty rather \
than guess. If the question cannot be resolved from the information available today, \
say so and give your best assessment. No generic padding."""


def condition_name(groups: set[str]) -> str:
    """Filesystem-safe condition name encoding the active artifact groups."""
    missing = set(ALL_GROUPS) - groups
    if not missing:
        return "snapshot_agent"
    if len(groups) == 1:
        return f"snapshot_agent-only_{next(iter(groups))}"
    if len(missing) == 1:
        return f"snapshot_agent-no_{next(iter(missing))}"
    return "snapshot_agent-groups_" + "+".join(sorted(groups))


def run_agent_loop(model: str, question: str, box: ToolBox, max_steps: int,
                   max_tokens: int) -> tuple[str, list[dict]]:
    """Tool-calling loop. Returns (final_answer, transcript)."""
    commit_note = (f" (checked out at commit {box.snap.commit_sha[:12]})"
                   if box.snap.commit_sha else "")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(
            repo=box.snap.repo, report_date=box.snap.report_time[:10],
            commit_note=commit_note)},
        {"role": "user", "content": question},
    ]
    tools = schemas_for(box.groups)
    transcript: list[dict] = []
    for step in range(1, max_steps + 1):
        resp = litellm.completion(model=model, messages=messages, tools=tools,
                                  max_tokens=max_tokens)
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None) or []
        if not tool_calls:
            final = (msg.content or "").strip()
            transcript.append({"step": step, "type": "final", "chars": len(final)})
            return final, transcript
        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [tc.model_dump() if hasattr(tc, "model_dump")
                                        else tc for tc in tool_calls]})
        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = box.execute(name, args)
            transcript.append({"step": step, "type": "tool", "tool": name,
                               "group": ToolBox.GROUP_OF_TOOL.get(name),
                               "args": args, "result": result})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
    # out of steps — force a final answer without tools
    messages.append({"role": "user", "content":
                     "You are out of tool budget. Give your final answer now."})
    resp = litellm.completion(model=model, messages=messages, max_tokens=max_tokens)
    final = (resp.choices[0].message.content or "").strip()
    transcript.append({"step": max_steps + 1, "type": "final_forced",
                       "chars": len(final)})
    return final, transcript


def run(input_path: Path, output_dir: Path, model: str, groups: set[str],
        condition: str, force: bool, limit: int | None, include_unapproved: bool,
        max_steps: int, max_tokens: int) -> None:
    threads = load_benchmark(input_path)
    items = iter_items(threads, include_unapproved)
    if limit:
        items = items[:limit]
    if not items:
        raise SystemExit(f"No eval items found in {input_path}.")

    run_name = f"{slugify(model)}_{condition}"
    output_path = output_dir / f"answers_{run_name}.jsonl"
    transcripts_dir = output_dir / "transcripts" / run_name
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    done: set[str] = set()
    if output_path.exists() and not force:
        done = {r["qid"] for r in load_jsonl(output_path) if not r.get("error")}
        print(f"Resuming: {len(done)} answers already in {output_path}")

    print(f"Model: {model} | condition: {condition} | groups: {sorted(groups)} "
          f"| items: {len(items)}")
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
                "condition": condition, "model": model,
                "knowledge_type": pair.get("knowledge_type"),
                "question": pair["question"],
                "answered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            try:
                snap = build_snapshot(thread["thread_id"], groups)
                box = ToolBox(snap, groups)
                text, transcript = run_agent_loop(model, pair["question"], box,
                                                  max_steps, max_tokens)
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
                print(f"ok ({len(box.calls)} tool calls, {len(text)} chars)")
            except Exception as exc:
                rec["error"] = str(exc)
                n_err += 1
                print(f"ERROR: {exc}")
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            if i < len(items) - 1:
                time.sleep(0.3)

    print(f"\nDone: {n_new} new answers, {len(done)} skipped, {n_err} errors")
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
    ap.add_argument("--max-steps", type=int, default=15,
                    help="max tool-calling rounds before a forced final answer")
    ap.add_argument("--max-tokens", type=int, default=2000)
    ap.add_argument("--force", action="store_true")
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
        condition_name(groups), args.force, args.limit,
        args.include_unapproved, args.max_steps, args.max_tokens)


if __name__ == "__main__":
    main()
