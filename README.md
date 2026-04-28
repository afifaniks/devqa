# Developer Questions Mining Pipeline

## Architecture

```
pipeline/
├── config.py              # Repo list, API token, output paths
├── run_all.py             # Master script — runs everything in order
├── miners/
│   ├── issues.py          # Mines issues, comments, events, duplicates
│   ├── commits.py         # Mines commit history, blame, SZZ
│   ├── pull_requests.py   # Mines PRs, reviews, linkage
│   ├── ci_runs.py         # Mines GitHub Actions run history
│   └── contributors.py    # Mines contributor activity graph
├── utils/
│   ├── github_client.py   # Rate-limit-aware GitHub API wrapper
│   └── storage.py         # Saves/loads JSON output
└── output/                # One folder per repo
    └── microsoft__vscode/
        ├── issues.jsonl
        ├── commits.jsonl
        ├── pull_requests.jsonl
        ├── ci_runs.jsonl
        └── contributors.jsonl
```

## Setup

```bash
pip install requests pydriller python-dotenv tqdm
```

Create a `.env` file:
```
GITHUB_TOKEN=ghp_your_token_here
```

## Running

```bash
# Mine everything for all configured repos
python run_all.py

# Mine only one artifact type
python miners/issues.py --repo microsoft/vscode

# Mine a specific repo only
python run_all.py --repo microsoft/vscode
```

## Output Format

Every miner writes newline-delimited JSON (`.jsonl`) — one record per line.
This makes it easy to process with pandas or stream large files without
loading everything into memory.

## Rate Limits

GitHub REST API: 5,000 requests/hour with a token.
The client in utils/github_client.py handles this automatically —
it checks remaining quota before each request and sleeps if needed.
