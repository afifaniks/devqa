# CLAUDE.md — Project context for AI assistants

## What this project is

A research pipeline that mines GitHub repositories and produces a labelled dataset of **developer information needs** — questions developers ask about their own codebase during software development. Each question is mapped to one of 78 question types (Q1–Q78) in a taxonomy covering 11 categories. The dataset is intended for training or evaluating LLM-based developer tools (e.g. a "ask your repo" assistant).

## Environment

- **Conda env**: `/local/home/amamun/envs/devqa` — always use this Python
- **Python binary**: `/local/home/amamun/envs/devqa/bin/python`
- **Shell**: tcsh (not bash); activate env with full path, not `conda activate`
- **`.env`** at project root holds `GITHUB_TOKEN` / `GITHUB_TOKENS`
- **Ollama** must be running locally (`ollama serve`) for LLM classification

## Repository structure

```
pipeline/
  config.py              — repos list, token loading, constants
  run_all.py             — master runner, orchestrates all miners
  miners/
    issues.py            — GitHub issues + comments (GraphQL)
    pull_requests.py     — PRs, reviews, linkage
    commits.py           — commit history, blame, SZZ fault-introduction
    ci_runs.py           — GitHub Actions run history
    contributors.py      — contributor activity, file experts, ownership
    mine_threads.py      — formats issues+discussions into raw_threads.jsonl
    qa_builder.py        — structured (question, ground_truth, artifacts) triples
  classification/
    classify.py          — two-stage LLM classifier → natural_qa_pairs.jsonl
  utils/
    github_client.py     — rate-limit-aware REST + GraphQL wrapper
    ollama_client.py     — Ollama client, JSON mode, STAGE1/STAGE2_MODEL constants
    storage.py           — load_jsonl, save_jsonl, append_record, checkpoints
    taxonomy.py          — full 78-question taxonomy string for LLM prompts

output/<owner>__<repo>/  — one folder per repo, named with / → __
  raw_threads.jsonl      — issue+discussion threads as flat text (mine_threads.py)
  natural_qa_pairs.jsonl — LLM-classified Q&A pairs (classify.py)
  qa_pairs.jsonl         — deterministic ground-truth pairs (qa_builder.py)
  issues.jsonl, pull_requests.jsonl, commits.jsonl, ...
  .checkpoint_*.json     — incremental progress checkpoints (hidden files)

review_ui/
  app.py                 — FastAPI app, serves on port 8765
  templates/index.html   — single-page review UI (vanilla JS)

summarize_qa_pairs.py    — CLI: counts question instances across all repos
verified_state.json      — human verification decisions, keyed by pair index
verified_qa_pairs.jsonl  — accepted pairs exported from the review UI
```

## The two output types

**natural_qa_pairs.jsonl** — produced by `classify.py` using a local LLM. Each record is a verbatim Q&A exchange extracted from a real GitHub thread, tagged with `question_id`, `confidence` (product of two stages), `reasoning`, and the full `thread_text`. These need human review via the UI.

**qa_pairs.jsonl** — produced by `qa_builder.py` from structured JSONL. Each record has a deterministic `ground_truth` (e.g. exact SHA, login) and `artifacts_needed`. Used for automatic evaluation.

## Classification pipeline

Two-stage LLM approach in `classification/classify.py`:
1. **Stage 1**: broad category (A–K or N) + contains_qa boolean
2. **Stage 2**: specific question ID within the category + extract verbatim Q&A

Both stages use Ollama's JSON format mode. Models are set in `utils/ollama_client.py` as `STAGE1_MODEL` and `STAGE2_MODEL` (currently `qwen3.6:latest`). Confidence is the product of both stage scores; default threshold is 0.55 (CLI default is 0.7).

Classification is resumable via `.checkpoint_classify_*.json` files. `--force` re-classifies from scratch.

## Taxonomy

78 questions, Q1–Q78, grouped A–K. Full descriptions in `utils/taxonomy.py` and `classification/classify.py`. Key categories:
- **A** People & awareness (Q1–Q7)
- **B** Code changes (Q8–Q27)
- **C** Work item progress (Q28–Q31)
- **F** Pull requests (Q47–Q52)
- **G** Bug management (Q53–Q60)
- **J** Onboarding (Q69–Q72)

Note: Q38–Q46 exist in `taxonomy.py` but are not in the active `CATEGORIES` dict in `classify.py` — they are considered obsolete or organisational and not currently classified.

## Review UI

FastAPI app at `review_ui/app.py`, running on port 8765.

```bash
cd review_ui
/local/home/amamun/envs/devqa/bin/python app.py
```

Key API endpoints:
- `GET /api/pairs` — filtered/paginated list (repo, question_id, status, text search)
- `GET /api/pairs/{index}` — full record including thread_text
- `POST /api/pairs/{index}/verify` — `{"status": "accepted"|"rejected"|"pending", "note": "..."}`
- `GET /api/stats` — counts and breakdown
- `POST /api/export` + `GET /api/export/download` — write and download verified_qa_pairs.jsonl

Verification state is persisted to `verified_state.json` (project root) after every decision.

The HTML is served directly as a static string (no Jinja2 template variables used) — the newer Starlette version changed the `TemplateResponse` API.

## Common tasks

**Summarise current output:**
```bash
/local/home/amamun/envs/devqa/bin/python summarize_qa_pairs.py
```

**Mine a new repo:**
```bash
cd pipeline
/local/home/amamun/envs/devqa/bin/python run_all.py --repo owner/repo
/local/home/amamun/envs/devqa/bin/python classification/classify.py --repo owner/repo
```

**Re-classify with different model:**
```bash
/local/home/amamun/envs/devqa/bin/python classification/classify.py \
  --repo psf/requests --stage1-model mistral:7b --force
```

**Start review UI:**
```bash
cd review_ui
/local/home/amamun/envs/devqa/bin/python app.py
# open http://localhost:8765
```

## Currently mined repos

| Repo | Output folder |
|---|---|
| `fastapi/fastapi` | `output/fastapi__fastapi/` |
| `psf/requests` | `output/psf__requests/` |
| `microsoft/vscode` | `output/microsoft__vscode/` (issues only so far) |

`config.py` currently has only `microsoft/vscode` in the `REPOS` list — the fastapi and requests data was mined earlier. Update `REPOS` to add new targets.

## Things to be aware of

- All JSONL files use `repo` field as `"owner/repo"` (slash), but output folder names use `owner__repo` (double underscore).
- Checkpoints are hidden `.checkpoint_*.json` files inside each output folder. Delete them (or use `--force`) to re-run a miner from scratch.
- The `qa_builder.py` produces pairs for a specific subset of questions (Q18, Q19, Q32, Q33, Q50, Q53, Q54, Q56) — questions that have deterministic ground truth from structured data. The remaining questions are covered only by the LLM classifier path.
- `mine_threads.py` must run before `classify.py` — it reads from `issues.jsonl` and the GitHub Discussions GraphQL API.
- `contributors.py` must run after `commits.py`, `issues.py`, and `pull_requests.py`.
