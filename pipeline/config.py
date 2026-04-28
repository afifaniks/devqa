import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKENS = [t.strip() for t in os.getenv("GITHUB_TOKENS", "").split(",") if t.strip()]
if not GITHUB_TOKENS and os.getenv("GITHUB_TOKEN"):
    GITHUB_TOKENS = [os.getenv("GITHUB_TOKEN")]

# Repositories to mine — add more here as you expand
REPOS = [
    "microsoft/vscode",
    # "facebook/react",
    # "torvalds/linux",
]

# How many items to fetch per page (max 100 for GitHub API)
PAGE_SIZE = 100

# Output directory
OUTPUT_DIR = "output"

# For issues miner — only fetch issues with these labels
# Empty list = fetch all issues
BUG_LABELS = []

# Minimum comment length to treat as meaningful ground truth (chars)
MIN_COMMENT_LENGTH = 100

# For SZZ — how many days before a fix commit to search for inducing commits
SZZ_WINDOW_DAYS = 365
