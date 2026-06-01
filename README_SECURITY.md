# Security Q&A Mining Pipeline

A sub-pipeline that extracts **developer security information needs** from public OSS GitHub threads. Unlike the main taxonomy pipeline (Q1–Q78), security pairs are not mapped to a fixed enum — they use a free-text `security_topic` for later open/axial coding into a security-specific taxonomy.

Output: `output/<owner>__<repo>/security_qa_pairs.jsonl` (pushed to git; other sibling files are ignored).

---

## How it works

```
raw_threads.jsonl   (produced by mine_threads.py)
        │
        ▼
Stage 0 — pre-filter: drop threads with < 2 non-bot substantive comments
        │
        ▼
Stage 1 — LLM (N-sample self-consistency)
          Decide: does this thread contain a security information need
          with a concrete, anchored answer?
          → contains_qa: true/false, need_summary, confidence
        │
        ▼
Stage 1.5 — regex pre-pass
          Extract CVE/GHSA/CWE/OSV IDs, version strings, PR refs,
          commit SHAs, advisory URLs (with comment provenance).
          Passed to Stage 2 as candidate list.
        │
        ▼
Stage 2 — LLM
          Extract verbatim question + answer, artifacts_needed,
          hard_facts (structured identifiers), security_topic,
          answerer_role.
        │
        ▼
Acceptance gate
  - answer < 30 chars                         → drop
  - no hard_facts AND artifacts empty/none    → drop (no grading anchor)
  - 30–99 chars AND no hard_facts             → drop (thin, source-only)
  - otherwise                                 → append to security_qa_pairs.jsonl
```

Self-consistency (Stage 1) runs N independent samples and majority-votes `contains_qa`. Default N=3. Set `--stage1-samples 1` to disable.

---

## Requirements

### 1. Conda environment

The project uses a shared conda env at `/local/home/amamun/envs/devqa`.

To recreate it from scratch (if needed):

```bash
conda create -p /local/home/amamun/envs/devqa python=3.11
/local/home/amamun/envs/devqa/bin/pip install \
    fastapi uvicorn[standard] python-dotenv requests tqdm
```

Always use the full path — do not rely on `conda activate` in tcsh:

```bash
/local/home/amamun/envs/devqa/bin/python --version
```

### 2. GitHub token

Create a `.env` file in the project root (one token is enough for reading):

```
GITHUB_TOKEN=ghp_your_token_here
```

For higher throughput during mining, use multiple tokens:

```
GITHUB_TOKENS=ghp_token1,ghp_token2,ghp_token3
```

### 3. Ollama (LLM backend)

Ollama must be running locally. The security classifier uses the model configured in `utils/ollama_client.py` (`STAGE1_MODEL` — currently `qwen3:6b` or similar).

```bash
# Install Ollama if not already installed
# https://ollama.com/download

# Start the server
ollama serve

# Pull the model (check utils/ollama_client.py for the current model name)
ollama pull qwen3:6b
```

Verify Ollama is up:

```bash
curl http://localhost:11434/api/tags
```

---

## Step-by-step: mine a new repo and generate security pairs

### Step 1 — Add the repo to config

Edit `pipeline/config.py` and add your repo to the `REPOS` list:

```python
REPOS = [
    "owner/repo",   # add here
    ...
]
```

### Step 2 — Mine GitHub artifacts

```bash
cd pipeline
/local/home/amamun/envs/devqa/bin/python run_all.py --repo owner/repo
```

This produces `issues.jsonl`, `pull_requests.jsonl`, `commits.jsonl`, etc. in `output/owner__repo/`.

Skip slow CI mining on large repos:

```bash
/local/home/amamun/envs/devqa/bin/python run_all.py --repo owner/repo --skip-ci
```

### Step 3 — Build raw threads

If you only need the security pipeline (not the full taxonomy pipeline), you can run `mine_threads.py` directly instead of `run_all.py`:

```bash
/local/home/amamun/envs/devqa/bin/python miners/mine_threads.py --repo owner/repo
```

This reads `issues.jsonl` and GitHub Discussions and writes `raw_threads.jsonl`.

### Step 4 — Run the security detector

```bash
cd pipeline
/local/home/amamun/envs/devqa/bin/python classification/detect_security_qa.py --repo owner/repo
```

Common options:

```bash
# Limit threads (for testing)
--limit 200

# Stop after extracting N pairs
--max-pairs 100

# Re-run from scratch (ignores checkpoint)
--force

# Only process open issues
--state open

# Disable self-consistency (faster, less accurate)
--stage1-samples 1

# Use a different model
--model mistral:7b

# Adjust confidence threshold (default 0.3 — recall-favoring)
--confidence 0.5
```

Full example:

```bash
/local/home/amamun/envs/devqa/bin/python classification/detect_security_qa.py \
    --repo psf/requests \
    --limit 500 \
    --max-pairs 80 \
    --stage1-samples 3
```

Progress is checkpointed automatically in `output/owner__repo/.checkpoint_detect_security_qa_*.json`. Re-running without `--force` resumes from where it left off.

---

## Labelling pairs

This is the human-in-the-loop step. Each pair produced by the detector has `status: pending`. You read the thread, judge quality, and mark it accepted or rejected. The `note` field is also where you record your open-coding label (your own security topic phrase) when the LLM-generated `security_topic` is wrong or too coarse.

### Start the review UI

```bash
cd review_ui
/local/home/amamun/envs/devqa/bin/python app.py
```

Open **http://localhost:8765/security** in a browser.

The main review UI at `/` covers the taxonomy pipeline. Security pairs are at `/security`.

### Labelling workflow

**1. Filter the queue**

Use the sidebar filters to scope your session:
- **Repo** — focus on one repo at a time
- **Status** — set to `pending` to see only unlabelled pairs
- **Confidence** — start with `HIGH` to process the clearest cases first
- **Search** — free text across question, answer, and security topic

**2. Read each pair**

The detail pane shows:
- **Security Topic** — LLM-generated free-text phrase (what Stage 2 thought the pair is about)
- **Need Summary** — one sentence from Stage 1 describing the security need and its grading anchor
- **Hard Facts** — CVE/GHSA/CWE/OSV IDs, fixed/affected versions, fix PRs, fix commits, advisory URLs
- **Extracted Question** — verbatim text copied from the thread
- **Extracted Answer** — verbatim text; check it actually answers the question and rests on a concrete anchor
- **Artifacts Needed** — what an LLM agent would need to answer this
- **Answerer Role** — `maintainer`, `contributor`, `commenter`, `op_self`, or `bot`
- **Original Thread** — full thread with comments labelled `[c0]`, `[c1]`, etc.

**3. Decide: accept or reject**

| Decision | When |
|---|---|
| **Accept** | The question is a genuine security information need; the answer is concrete (has an identifier or citable source); the extracted Q and A text accurately reflect what the thread says. |
| **Reject** | False positive (not actually security); answer is deflection / pure opinion / unanchored; extracted Q or A text is garbled or wrong; thread is a config question with no risk angle. |

Controls (bottom of the detail pane):
- **✓ Accept** button — or press `a`
- **✗ Reject** button — or press `r`
- **↩ Reset** button — or press `u` — returns to `pending`
- `j` / `k` — navigate to next/previous pair

Decisions save immediately to `security_verified_state.json`. No submit needed.

**4. Write a note (open coding)**

The **Notes** textarea (above the buttons) is for your open-coding label. Use it to:
- Correct a wrong `security_topic` — write your own phrase
- Record why you rejected (e.g. "deflection — maintainer said ask Stripe support")
- Flag borderline pairs for discussion (e.g. "borderline: config Q but risk angle exists")
- Note grading difficulty (e.g. "hard_facts present but fixed_version is a range, not exact")

The note is stored in `security_verified_state.json` and exported with accepted pairs.

**5. What makes a good accept / reject decision**

Accept when ALL of these hold:
- The question is clearly about a security risk, vulnerability, or security-relevant behaviour in *this project* (not just using a security-named API)
- The answer rests on a concrete anchor: a CVE/GHSA/version string/commit SHA/advisory URL, or a citable source (project docs, RFC, scanner rule, linked prior incident)
- The verbatim Q and A text in the pair accurately represent the thread (check against the original thread below)
- The pair would be useful to someone building or evaluating an LLM security assistant for this repo

Reject when ANY of these hold:
- PEM/key file-format usage error whose answer is just "your file is malformed"
- Browser-storage or cross-site cookie deflection ("browser behaviour, not our library")
- Config question that touches a security-named flag but asks no security question
- "Wrong forum / ask Discord / ask Stripe support" deflection with no security content
- Pure regression bug whose only security link is a method name containing "auth" or "sign"
- Answer is opinion without a source: "we don't consider this exploitable" with nothing further
- Extracted Q or A is truncated, garbled, or pulled from the wrong comment

### Progress tracking

The header shows `accepted / rejected / pending` counts. The stats page (`/security/stats`) breaks down counts by repo and security topic.

### Export accepted pairs

After labelling, export the accepted set:

Via the UI: click **Export** on the `/security` page, then **Download**.

Via API:

```bash
curl -X POST http://localhost:8765/api/security/export
curl http://localhost:8765/api/security/export/download -o security_verified_qa_pairs.jsonl
```

Output: `security_verified_qa_pairs.jsonl` in the project root. Contains full records (including `note`, `verified_at`, all `hard_facts`) for all accepted pairs across all repos.

---

## Currently mined repos

| Repo | Output folder | Notes |
|---|---|---|
| `psf/requests` | `output/psf__requests/` | |
| `fastapi/fastapi` | `output/fastapi__fastapi/` | |
| `expressjs/express` | `output/expressjs__express/` | |
| `rails/rails` | `output/rails__rails/` | |
| `stripe/stripe-node` | `output/stripe__stripe-node/` | |
| `urllib3/urllib3` | `output/urllib3__urllib3/` | |
| `pyca/cryptography` | `output/pyca__cryptography/` | |
| `axios/axios` | `output/axios__axios/` | |
| `auth0/node-jsonwebtoken` | `output/auth0__node-jsonwebtoken/` | |
| `python-pillow/Pillow` | `output/python-pillow__Pillow/` | |
| `django/django` | `output/django__django/` | |

---

## Output format: security_qa_pairs.jsonl

One record per line. Key fields:

| Field | Description |
|---|---|
| `source` | `"issue"` or `"discussion"` |
| `repo` | `"owner/repo"` |
| `number` | Issue/discussion number |
| `url` | GitHub URL |
| `state` | `"open"` or `"closed"` |
| `question_id` | Always `"SECURITY_OPEN"` (open coding — no fixed enum) |
| `need_summary` | One sentence from Stage 1 describing the security need and its anchor |
| `security_topic` | Short free-text phrase from Stage 2 for open/axial coding |
| `question_text` | Verbatim question copied from the thread |
| `answer_text` | Verbatim answer copied from the thread |
| `question_author` | GitHub login of the question author |
| `answer_author` | GitHub login of the answerer |
| `answerer_role` | `maintainer`, `contributor`, `commenter`, `op_self`, or `bot` |
| `artifacts_needed` | List of artifact types needed to answer (see below) |
| `hard_facts` | Structured identifiers extracted by Stage 2 (see below) |
| `references` | Flat list: CVE/GHSA/CWE/OSV IDs + advisory URLs (backward compat) |
| `stage1_confidence` | `HIGH`, `MEDIUM`, or `LOW` |
| `stage1_n_yes` | How many Stage 1 samples voted `contains_qa=true` |
| `stage1_n_samples` | Total Stage 1 samples run |
| `stage2_confidence` | `HIGH`, `MEDIUM`, or `LOW` |
| `confidence` | Numeric score: stage1_conf × stage2_conf (0–1) |
| `model` | Ollama model used |
| `thread_text` | Full original thread text |
| `comments` | Raw comment list with `id`, `author`, `timestamp`, `body` |

### hard_facts schema

```json
{
  "cve_ids":           ["CVE-2023-32681"],
  "ghsa_ids":          ["GHSA-xxxx-xxxx-xxxx"],
  "cwe_ids":           ["CWE-601"],
  "osv_ids":           ["PYSEC-2023-74"],
  "fixed_versions":    ["2.29.0"],
  "affected_versions": ["< 2.29.0"],
  "fix_prs":           ["#6655"],
  "fix_commits":       ["abc1234"],
  "advisory_urls":     ["https://github.com/psf/requests/security/advisories/GHSA-xxxx"]
}
```

Empty lists mean no identifier of that type was found. Grading strategy downstream:
- `hard_facts` populated → deterministic grading (identifier match)
- `hard_facts` empty, `artifacts_needed` non-empty → source-anchored judge

### artifacts_needed values

General: `code`, `commit_history`, `issue_tracker`, `pr_data`, `ci_logs`, `contributor_data`, `documentation`, `external_reference`

Security-specific: `advisory`, `cve_cwe_db`, `dependency_manifest`, `security_scan_logs`, `prior_incident`

---

## Troubleshooting

**"Ollama not running"** — run `ollama serve` in a separate terminal.

**Empty output / all threads dropped** — check `raw_threads.jsonl` exists and has substantive threads. Run `mine_threads.py` first if missing.

**Checkpoint not resuming** — checkpoint file is keyed by model name. If you change `--model`, a new checkpoint is created. Use `--force` to start fresh.

**High drop rate at "no_anchor"** — the model is not extracting hard facts or artifacts. Try a larger/better model via `--model`. The 0.3 default confidence threshold is already recall-favoring; the anchor gate is a hard quality check that cannot be lowered.

**Slow on large repos** — use `--state open` to process only open issues first (usually fewer, more active threads), or `--limit N` for a quick test run.
