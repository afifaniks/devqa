"""
SecDevQA harness — web UI: launch evaluation runs and monitor them live.

A standalone FastAPI app (port 8766) over harness/output/, distinct from the
benchmark/review UI (review_ui/app.py, port 8765). Three halves:

  * Launcher — pick a system (bare LLM / built-in snapshot agent / claude-code /
    opencode), model, artifact-group context selection, limit, and optional
    auto-grading; the server spawns the corresponding `python -m harness ...` CLI
    as a subprocess (logged to harness/output/logs/).
  * Monitor — read-only polling over the answers_*/grades_* JSONL files and
    transcripts; tolerant of half-written lines, needs no coordination with runs.
  * Compare — per-question matrix across selected runs (GET /api/compare).

Usage:
  python -m harness ui              # http://localhost:8766
  python -m harness ui --port 9000
"""

from __future__ import annotations

import argparse
import logging

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from harness.core.paths import UI_DIR

from . import benchmark, compare, launcher, runs

DIST_DIR = UI_DIR / "dist"
HTML_FILE = DIST_DIR / "index.html"
DEFAULT_PORT = 8766

_BUILD_HINT = (
    "<html><body style='font-family:system-ui;background:#0b0e14;color:#e6eaf2;"
    "padding:60px;line-height:1.6'><h2>Harness UI not built</h2><p>The React app "
    "under <code>harness/ui/</code> hasn't been built yet. From that directory run:"
    "</p><pre style='background:#19202e;padding:14px;border-radius:8px'>"
    "npm install\nnpm run build</pre><p>then reload. For live development instead, "
    "run <code>npm run dev</code> (proxies the API to this server on :8766).</p>"
    "</body></html>"
)

_QUIET_POLL_PATHS = (
    "/api/runs", "/api/procs", "/api/compare", "/api/transcript", "/api/live"
)


class _QuietPollingFilter(logging.Filter):
    """Suppress successful poll requests from uvicorn's access log."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 5:
            path, status = str(args[2]), args[4]
            if (
                isinstance(status, int)
                and 200 <= status < 400
                and path.startswith(_QUIET_POLL_PATHS)
            ):
                return False
        return True


app = FastAPI(title="SecDevQA — evaluation harness")

app.include_router(runs.router)
app.include_router(benchmark.router)
app.include_router(compare.router)
app.include_router(launcher.router)

if DIST_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(DIST_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def page():
    if not HTML_FILE.exists():
        return HTMLResponse(_BUILD_HINT, status_code=503)
    return HTMLResponse(HTML_FILE.read_text(encoding="utf-8"))


def main() -> None:
    import uvicorn

    ap = argparse.ArgumentParser(description="Harness web UI (launcher + monitor).")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument(
        "--verbose-access",
        action="store_true",
        help="Log every request, including the UI's live polling.",
    )
    args = ap.parse_args()
    if not args.verbose_access:
        logging.getLogger("uvicorn.access").addFilter(_QuietPollingFilter())
    print(f"SecDevQA harness UI → http://localhost:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
