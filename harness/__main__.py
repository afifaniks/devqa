"""
SecDevQA evaluation harness — a self-contained benchmarking module.

  python -m harness answer    [...]   bare-LLM no_context condition (harness/answer.py)
  python -m harness agent     [...]   built-in snapshot_agent, typed tools (harness/agent.py)
  python -m harness external  [...]   off-the-shelf agents (claude-code, opencode) in a
                                      time-capped sandbox (harness/external.py)
  python -m harness grade     [...]   condition-aware grading (harness/grade.py)
  python -m harness ui        [...]   web UI: launch runs + live monitoring (harness/monitor.py)

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
        from harness import answer
        answer.main()
    elif cmd == "agent":
        from harness import agent
        agent.main()
    elif cmd == "external":
        from harness import external
        external.main()
    elif cmd == "grade":
        from harness import grade
        grade.main()
    elif cmd in ("ui", "monitor", "serve"):
        from harness import monitor
        monitor.main()
    else:
        print(f"Unknown command: {cmd}\n{USAGE}")
        sys.exit(2)


if __name__ == "__main__":
    main()
