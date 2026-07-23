"""
SecDevQA evaluation harness — a self-contained benchmarking module.

  python -m harness answer       [...]   bare-LLM no_context condition (conditions/answer.py)
  python -m harness agent        [...]   built-in snapshot_agent, typed tools (conditions/agent.py)
  python -m harness coding-agent [...]   off-the-shelf coding agent (claude-code) in a per-item
                                         podman container over the unified MCP snapshot interface,
                                         egress-locked (container/run.py)
  python -m harness grade     [...]   condition-aware grading (grading/grade.py)
  python -m harness ui        [...]   web UI: launch runs + live monitoring (monitor/ package)

The harness consumes dataset/security_benchmark_final.jsonl (+ mined corpora as data
files) and writes to harness/output/. It does not import benchmark-construction code.
"""

from __future__ import annotations

import sys

USAGE = __doc__


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(USAGE)
        sys.exit(0)
    cmd, rest = sys.argv[1], sys.argv[2:]
    sys.argv = [f"harness {cmd}"] + rest
    if cmd == "answer":
        from harness.conditions import answer
        answer.main()
    elif cmd == "agent":
        from harness.conditions import agent
        agent.main()
    elif cmd in ("coding-agent", "coding_agent"):
        from harness.container import run as coding_agent_run
        coding_agent_run.main()
    elif cmd == "grade":
        from harness.grading import grade
        grade.main()
    elif cmd in ("ui", "monitor", "serve"):
        from harness import monitor
        monitor.main()
    else:
        print(f"Unknown command: {cmd}\n{USAGE}")
        sys.exit(2)


if __name__ == "__main__":
    main()
