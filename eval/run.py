"""
Thin CLI dispatch for the SecDevQA evaluation harness.

Subcommands:
  normalize   — Stage 1: draft eval_questions from benchmark (normalize_questions.py)
  generate    — Stage 2: run models on approved eval_questions (generate.py)

Examples:
  python -m eval.run normalize --benchmark dataset/security_benchmark.jsonl
  python -m eval.run normalize --mock
  python -m eval.run generate --models gpt-4o --resume --mock
"""

import sys


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]
    sys.argv = [f"eval.{cmd}"] + sys.argv[2:]

    if cmd == "normalize":
        from eval.normalize_questions import main as _main
        _main()
    elif cmd == "generate":
        from eval.generate import main as _main
        _main()
    else:
        print(f"Unknown subcommand: {cmd!r}. Use 'normalize' or 'generate'.")
        sys.exit(1)


if __name__ == "__main__":
    main()
