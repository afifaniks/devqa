# Harness UI

The web front-end for the SecDevQA evaluation harness — a **Vite + React + [Mantine]**
single-page app. Two tabs: **Monitor** (launch evaluations and watch them run, live) and
**Compare** (browse predictions for several runs side by side, with gradings).

It is served by the harness FastAPI server (`../monitor.py`) and talks to it over the
`/api/*` endpoints. This is a separate app from the benchmark review UI (`review_ui/`).

[Mantine]: https://mantine.dev

## Develop

```bash
npm install
npm run dev        # Vite dev server on :5173, proxies /api → FastAPI on :8766
```

Run the API server alongside it (`python -m harness ui` from the repo root). The dev
server hot-reloads on save; the API proxy means you don't need to rebuild to see changes.

## Build (what the server serves)

```bash
npm run build      # → dist/  (referenced under /static/, see vite.config.js)
```

`monitor.py` serves `dist/index.html` at `/` and `dist/assets/*` at `/static/assets/*`.
`dist/` is gitignored — rebuild after pulling.

## Layout

```
src/
  main.jsx              app entry — MantineProvider + theme, dark scheme
  theme.js              Mantine theme + VERDICT_COLOR map (the verdict palette)
  global.css            page backdrop, verdict spine, line-clamp, comparison grid
  api.js                typed wrapper over the /api/* endpoints (one fn per route)
  hooks/
    usePolling.js       live data: fetch on mount + interval, pause when tab hidden
  lib/
    outcomes.js         OUTCOME_ORDER, outcomeOf(), dominantOutcome(), claimColor()
    format.js           age(), pct()
    stats.js            computeStats() — per-run accuracy/score/hallucination/facts/tools
  components/
    App.jsx             shell: header, tabs, global runs/procs polling
    MonitorView.jsx     launcher + processes + run list
    Launcher.jsx        launch form → POST /api/launch
    ProcessList.jsx     live process cards with streaming log tail
    RunCard.jsx         one run (verdict spine, progress, live item polling when open)
    RunItem.jsx         per-item question/response/facts/claims/transcript
    SectionLabel.jsx    quiet uppercase section heading
    FactChips.jsx       hard-fact verdict chips (shared)
    compare/
      CompareView.jsx   orchestration: selection, live compare polling, filtering
      RunPicker.jsx     multi-select run cards
      FilterBar.jsx     knowledge-type / outcome / repo / search / toggles
      CompareStats.jsx  stat cards + charts (@mantine/charts): accuracy by knowledge
                        type, hard-fact match rate, tool calls by group
      CompareGrid.jsx   the side-by-side matrix + expandable row detail
      DetailColumn.jsx  one run's full prediction inside an expanded row
```

## Design notes

This is a **security-evaluation instrument**, not a marketing page. The grading verdict
colors — correct (teal) / partial (yellow) / incorrect (red) — are the signature visual
language and appear as badges, as the summary bars, and as the verdict spine down each
run card. One calm azure carries interaction; everything else stays quiet. Type pairs
**IBM Plex Mono** for data (qids, CVE IDs, code) with **IBM Plex Sans** for chrome.

Live updates are intentionally **polling**, not websockets: `usePolling` re-fetches on an
interval, keeps the last good value through transient errors, and pauses while the tab is
hidden. It needs no coordination with the runs (which are plain CLI subprocesses), so it
survives an API restart and stays simple.
