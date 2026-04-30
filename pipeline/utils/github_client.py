import time
import requests
from config import GITHUB_TOKENS, PAGE_SIZE

BASE = "https://api.github.com"
_THRESHOLD = 50


class _TokenPool:
    def __init__(self, tokens):
        if not tokens:
            raise ValueError(
                "No GitHub tokens configured (set GITHUB_TOKENS or GITHUB_TOKEN)"
            )
        self._tokens = tokens
        self._sessions = [self._make_session(t) for t in tokens]
        self._remaining = [10_000] * len(tokens)  # optimistic until first response
        self._reset_at = [0] * len(tokens)
        self._idx = 0

    def _make_session(self, token):
        s = requests.Session()
        s.headers.update(
            {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        return s

    @property
    def session(self):
        return self._sessions[self._idx]

    def record(self, response):
        """Update rate-limit state from a response and rotate/sleep if needed."""
        self._remaining[self._idx] = int(
            response.headers.get("X-RateLimit-Remaining", 100)
        )
        self._reset_at[self._idx] = int(response.headers.get("X-RateLimit-Reset", 0))

        if self._remaining[self._idx] >= _THRESHOLD:
            return

        # Try rotating to a token with capacity
        for offset in range(1, len(self._tokens)):
            candidate = (self._idx + offset) % len(self._tokens)
            if self._remaining[candidate] >= _THRESHOLD:
                print(
                    f"  [rate limit] token[{self._idx}] has {self._remaining[self._idx]} left"
                    f" — rotating to token[{candidate}]"
                )
                self._idx = candidate
                return

        # All tokens are low — sleep until the soonest reset
        soonest_reset = min(self._reset_at)
        wait = max(soonest_reset - time.time() + 5, 0)
        print(
            f"  [rate limit] all {len(self._tokens)} token(s) exhausted"
            f" — sleeping {wait:.0f}s"
        )
        time.sleep(wait)
        self._remaining = [10_000] * len(self._tokens)  # reset optimistic after sleep


_pool = _TokenPool(GITHUB_TOKENS)


def get(path, params=None):
    """Single GET request. Raises on non-200."""
    url = path if path.startswith("http") else f"{BASE}{path}"
    response = _pool.session.get(url, params=params, timeout=30)
    _pool.record(response)
    response.raise_for_status()
    return response.json()


def paginate(path, params=None):
    """Yield all items across pages for a GitHub list endpoint."""
    params = {**(params or {}), "per_page": PAGE_SIZE}
    url = path if path.startswith("http") else f"{BASE}{path}"

    while url:
        response = _pool.session.get(url, params=params, timeout=30)
        _pool.record(response)
        response.raise_for_status()
        items = response.json()

        if isinstance(items, dict):
            items = items.get("items", [])

        yield from items

        url = response.links.get("next", {}).get("url")
        params = {}


_GRAPHQL_URL = f"{BASE}/graphql"


def graphql(query, variables=None):
    """Execute a single GraphQL query. Raises on HTTP or GraphQL errors."""
    response = _pool.session.post(
        _GRAPHQL_URL,
        json={"query": query, "variables": variables or {}},
        timeout=30,
    )
    _pool.record(response)
    response.raise_for_status()
    payload = response.json()
    if "errors" in payload:
        raise RuntimeError(f"GraphQL errors: {payload['errors']}")
    return payload.get("data", {})


def paginate_graphql(query, variables, get_page):
    """
    Yield nodes from a paginated GraphQL query.

    get_page(data) must return a dict with keys 'nodes', 'pageInfo'
    where pageInfo has 'hasNextPage' and 'endCursor'.
    """
    variables = {**variables}
    while True:
        data = graphql(query, variables)
        page = get_page(data)
        yield from page.get("nodes", [])
        if not page.get("pageInfo", {}).get("hasNextPage"):
            break
        variables["cursor"] = page["pageInfo"]["endCursor"]
