# CLAUDE.md — Project context for AI assistants

## What this project is

**SecDevQA** — a research benchmark and evaluation harness for developer security questions. The benchmark contains real Q&A pairs mined from GitHub security issues, filtered to pairs where the maintainer's answer contains at least one externally verifiable hard fact (CVE/GHSA ID, fixed version, fix commit/PR, advisory URL). The paper studies (a) a taxonomy of developer security question categories, (b) which artifact types maintainers draw on to answer each category, and (c) how well frontier LLMs and coding agents answer these questions under controlled context conditions.

Target venue: ICSE 2027.

## Environment

- **Conda env**: `/local/home/amamun/envs/devqa` — always use this Python
- **Python binary**: `/local/home/amamun/envs/devqa/bin/python`
- **Shell**: tcsh (not bash); activate env with full path, not `conda activate`
- **`.env`** at project root holds `GITHUB_TOKEN` / `GITHUB_TOKENS` and `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`
- **Ollama** must be running locally (`ollama serve`) for local LLM use

## Repository structure

```
dataset/
  security_benchmark.jsonl  — 125 hard-verifiable security Q&A pairs (primary artifact)
  open_codes.jsonl           — LLM-assigned open codes (output of open_coding/open_code.py)
  open_codes_verified.json   — human-verified codes (state file, keyed by record id)
  open_codes_verified.jsonl  — accepted codes export
  build.py                   — builds security_benchmark.jsonl from verified pairs + raw output
  repo_selector.py           — selects repos from GitHub Advisory Database for mining

open_coding/
  open_code.py               — LiteLLM-based open coding pipeline (any provider)

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
    openai_client.py     — OpenAI Responses API client with token-usage capture
    storage.py           — load_jsonl, save_jsonl, append_record, checkpoints
    taxonomy.py          — full 78-question taxonomy (legacy; not used for benchmark)

output/<owner>__<repo>/    — one folder per repo (/ → __)
  security_qa_pairs.jsonl  — extracted security pairs (input to build.py)
  raw_threads.jsonl        — issue+discussion threads as flat text
  issues.jsonl, pull_requests.jsonl, commits.jsonl, ...
  .checkpoint_*.json       — incremental progress checkpoints (hidden files)

eval/
  run.py                   — CLI dispatch (normalize, answer, grade)
  normalize_questions.py   — drafts eval_questions.jsonl from benchmark
  generate.py              — runs models against eval questions
  data.py                  — shared data loading helpers
  data/
    eval_questions.jsonl   — normalized questions for evaluation
  output/
    answers_*.jsonl        — model responses per run

review_ui/
  app.py                   — FastAPI app, port 8765
  templates/
    benchmark.html         — /benchmark  — browse/edit security_benchmark.jsonl
    open_coding.html       — /open-coding — verify/edit LLM open codes
    index.html             — /           — F&M classified pairs review
    chat.html              — /security/chat — LLM-assisted pair review
    stats.html             — /stats
    taxonomy.html          — /taxonomy

advisory-database/         — local clone of github/advisory-database (for repo_selector.py)
repo_candidates.csv        — repos passing the selection filter (output of repo_selector.py)
```

## The benchmark: security_benchmark.jsonl

Each record has:
- `id` — unique string: `owner/repo/issue/number`
- `repo`, `number`, `url`, `title`, `state`, `created_at`, `closed_at`, `labels`, `reporter`
- `question_comment_id`, `answer_comment_id` — IDs into the `comments` array
- `question_author`, `answer_author`, `answerer_role` — maintainer / contributor / commenter / op_self
- `artifacts_needed` — list: code, commit_history, pr_data, dependency_manifest, advisory, cve_cwe_db, documentation, external_reference
- `hard_facts` — dict: cve_ids, ghsa_ids, cwe_ids, osv_ids, fixed_versions, fix_prs, fix_commits, advisory_urls
- `qa_summary` — one-sentence LLM summary of the Q&A
- `security_topic` — short phrase naming the security concern
- `human_note` — first-author annotation explaining why the pair was accepted
- `llm_confidence` — extraction confidence score
- `comments` — full comment array with id, author, timestamp, body

## Open coding pipeline

Assigns inductive codes (noun phrases, 1–2 per pair) to each Q&A pair to build a security question taxonomy.

```bash
# Run with any LiteLLM provider
/local/home/amamun/envs/devqa/bin/python open_coding/open_code.py \
  --model openai/gpt-5.4-mini

/local/home/amamun/envs/devqa/bin/python open_coding/open_code.py \
  --model anthropic/claude-sonnet-4-6

/local/home/amamun/envs/devqa/bin/python open_coding/open_code.py \
  --model ollama/qwen3.6:latest --api-base http://localhost:11434

# Test first 5 records
/local/home/amamun/envs/devqa/bin/python open_coding/open_code.py \
  --model openai/gpt-5.4-mini --limit 5

# Force re-run
/local/home/amamun/envs/devqa/bin/python open_coding/open_code.py \
  --model openai/gpt-5.4-mini --force
```

Output: `dataset/open_codes.jsonl` (resumable — skips already-coded IDs).
Each record: `{id, repo, codes: [...], rationale, model}`.

Prompt feeds the LLM: issue title, issue body (c0), QA summary, artifacts needed, hard facts, full thread, and the focal Q&A exchange. `security_topic` is intentionally excluded to avoid anchoring.

## Review UI

FastAPI app on port 8765. Run from `review_ui/`:

```bash
cd review_ui
/local/home/amamun/envs/devqa/bin/python app.py
```

### Pages

| URL | Purpose |
|---|---|
| `/benchmark` | Browse and edit `security_benchmark.jsonl` records |
| `/open-coding` | Verify/edit LLM open codes; accept/reject each pair |
| `/` | F&M classified pairs review (legacy pipeline) |
| `/security/chat` | LLM-assisted review chat for security pairs |
| `/taxonomy` | Taxonomy reference |

### Key API endpoints

**Benchmark browser (`/api/benchmark/*`):**
- `GET /api/benchmark/records` — filtered/paginated list
- `GET /api/benchmark/records/{index}` — full record with comments
- `PATCH /api/benchmark/records/{index}` — edit qa_summary, security_topic, human_note, answerer_role, artifacts_needed, hard_facts, question/answer comment IDs

**Open coding review (`/api/oc/*`):**
- `GET /api/oc/records` — list with filter (repo, status, text search)
- `GET /api/oc/records/{index}` — full record (benchmark context merged with LLM codes)
- `POST /api/oc/records/{index}/save` — `{status, codes: [...], rationale, note}`
- `GET /api/oc/stats` — counts by status
- `POST /api/oc/export` + `GET /api/oc/export/download`
- `POST /api/oc/reload` — reload open_codes.jsonl without restart

State: `dataset/open_codes_verified.json` (keyed by record id string).
Export: `dataset/open_codes_verified.jsonl`.

## Mining pipeline (for expanding the benchmark)

```bash
# Mine a new repo
cd pipeline
/local/home/amamun/envs/devqa/bin/python run_all.py --repo owner/repo

# Run the security QA classifier
/local/home/amamun/envs/devqa/bin/python classification/classify.py --repo owner/repo
```

Output lands in `output/owner__repo/`. Then verify pairs in the review UI (`/security` pipeline) and rebuild the benchmark:

```bash
/local/home/amamun/envs/devqa/bin/python dataset/build.py
```

## Evaluation harness

```bash
# Normalize benchmark to eval questions
/local/home/amamun/envs/devqa/bin/python -m eval.run normalize \
  --benchmark dataset/security_benchmark.jsonl

# Run a model
/local/home/amamun/envs/devqa/bin/python -m eval.run answer \
  --model openai/gpt-4.1

# Grade responses
/local/home/amamun/envs/devqa/bin/python -m eval.run grade
```

## Things to be aware of

- `security_benchmark.jsonl` is the source of truth — edit records via the `/benchmark` UI, not by hand.
- `open_codes.jsonl` output filename is model-specific (`open_codes_gpt-5.4-mini.jsonl`) when using `--output`; default is `open_codes.jsonl`. The review UI always reads `dataset/open_codes.jsonl`.
- All JSONL files use `repo` as `"owner/repo"` (slash); output folder names use `owner__repo` (double underscore).
- Checkpoints are hidden `.checkpoint_*.json` files inside each output folder. Delete them (or use `--force`) to re-run a miner from scratch.
- `mine_threads.py` must run before `classify.py`.
- `contributors.py` must run after `commits.py`, `issues.py`, and `pull_requests.py`.
- The `human_note` field is the first-author's verification rationale — do NOT include it in open coding prompts (would anchor/bias the codes).
- `litellm` is installed in the devqa env; `anthropic` was added alongside it.
