"""
SecDevQA — typed tools the snapshot agent can call, grouped by artifact type.

One tool group per artifact type, so "which artifact types did the agent consult" is a
count of tool calls by name (RQ4 attribution by construction — PLAN.md Phase 4):

  code      read_file, list_dir, search_code          (worktree at commit-before-T)
  commits   git_log, git_show                         (history capped at T by checkout;
                                                       git_show guarded to ancestors)
  issues    search_issues, get_issue                  (corpus <= T, source thread excluded)
  prs       search_prs, get_pr                        (corpus <= T)
  advisory  search_advisories, get_advisory           (GHSA snapshot <= T)
            vuln_lookup                                (canonical CVE/GHSA/CWE record,
                                                       live id-resolution, all conditions)

`artifacts_needed` vocabulary maps onto groups via ARTIFACT_TO_GROUP; the LOO /
single-artifact toggles of the selective-provision design (RQ3) enable/disable groups.
Every tool result is truncated to MAX_RESULT_CHARS (except vuln_lookup, whose single
canonical record is curated/clipped per-field instead).

An OPTIONAL `web` group (web_search, web_fetch over the live public internet via
DuckDuckGo) is gated separately by ToolBox.web — it is NOT one of ALL_GROUPS and so is
never part of the artifact-provision design or the LOO/single-artifact conditions. It
deliberately breaks the time-cap, so runs that enable it carry a distinct `+web`
condition suffix (harness/agent.py).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from harness.core.paths import CACHE_DIR
from harness.snapshot.builder import Snapshot

MAX_RESULT_CHARS = 20000

VULN_CACHE = CACHE_DIR / "vuln"   # one curated JSON per looked-up id
HTTP_TIMEOUT = 20
PROSE_CLIP = 1500            # only verbose free-text fields are clipped, never facts/refs

# artifacts_needed value -> tool group
ARTIFACT_TO_GROUP = {
    "code": "code", "dependency_manifest": "code", "documentation": "code",
    "commit_history": "commits",
    "pr_data": "prs",
    "issue_tracker": "issues", "prior_incident": "issues",
    "advisory": "advisory", "cve_cwe_db": "advisory",
    "external_reference": None,        # live web — not available under the time-cap
    "security_scan_logs": None, "ci_logs": None, "contributor_data": None,
}
ALL_GROUPS = ("code", "commits", "issues", "prs", "advisory")


def _trunc(s: str, n: int = MAX_RESULT_CHARS) -> str:
    return s if len(s) <= n else s[:n] + f"\n... [truncated, {len(s)} chars total]"


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else f"ERROR: {r.stderr.strip()[:300]}"


def _html_to_text(html: str) -> str:
    """Strip a fetched HTML page down to readable text (drops script/style)."""
    try:
        from lxml import html as lxml_html
        doc = lxml_html.fromstring(html)
        for bad in doc.xpath("//script | //style | //noscript"):
            bad.getparent().remove(bad)
        text = doc.text_content()
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


# ---------------------------------------------------------------------------
# vuln_lookup — canonical id resolution (CVE / GHSA / CWE).
#
# Live but DETERMINISTIC from the agent's view: a given id resolves to the same
# canonical record. Sources (no API key): OSV.dev for GHSA + affected/fixed versions,
# NVD for CVE description/CVSS/CWE, MITRE CWE API for weakness definitions. Results are
# curated to the fields that matter (versions/refs/ids kept whole; only long prose is
# clipped) and cached on disk by id so reruns are reproducible and avoid rate limits.
# This is reference resolution, not web browsing — so it stays in the `advisory` group
# and is available in every condition (no time-cap gate: the agent only ever looks up
# ids it was given or derived, and the canonical record is not the thread's resolution).
# ---------------------------------------------------------------------------

def _clip(s: str, n: int = PROSE_CLIP) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[:n].rstrip() + " …[clipped]"


def _http_json(url: str, headers: dict | None = None) -> dict | None:
    try:
        import requests
        r = requests.get(url, timeout=HTTP_TIMEOUT,
                         headers={"User-Agent": "SecDevQA-agent", **(headers or {})})
    except Exception:
        return None
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except ValueError:
        return None


def _osv_fixed_and_affected(osv: dict) -> tuple[list[str], list[str]]:
    """Pull fixed versions and affected-package summaries out of an OSV record."""
    fixed, affected = [], []
    for a in osv.get("affected") or []:
        pkg = (a.get("package") or {})
        name = pkg.get("name") or ""
        eco = pkg.get("ecosystem") or ""
        for rng in a.get("ranges") or []:
            # GIT ranges carry commit SHAs as "fixed", not versions — skip for the
            # version list (the SEMVER/ECOSYSTEM range carries the real fixed version).
            if rng.get("type") == "GIT":
                continue
            intro = next((e["introduced"] for e in rng.get("events", [])
                          if "introduced" in e), None)
            fx = [e["fixed"] for e in rng.get("events", []) if "fixed" in e]
            fixed += fx
            if name:
                span = f"{eco}:{name}" if eco else name
                if intro or fx:
                    span += f" ({intro or '0'} → {', '.join(fx) or 'unfixed'})"
                affected.append(span)
        if name and not (a.get("ranges")):
            affected.append(f"{eco}:{name}" if eco else name)
    # de-dup, keep order
    return list(dict.fromkeys(fixed)), list(dict.fromkeys(affected))


def _parse_osv(osv: dict) -> dict:
    fixed, affected = _osv_fixed_and_affected(osv)
    sev = []
    for s in osv.get("severity") or []:
        sev.append(f"{s.get('type', 'CVSS')}: {s.get('score', '')}")
    cwes = (osv.get("database_specific") or {}).get("cwe_ids") or []
    return {
        "id": osv.get("id"),
        "aliases": osv.get("aliases") or [],
        "summary": osv.get("summary") or "",
        "details": _clip(osv.get("details") or ""),
        "severity": sev,
        "cwe_ids": cwes,
        "affected": affected,
        "fixed_versions": fixed,
        "references": [r.get("url") for r in (osv.get("references") or []) if r.get("url")],
        "published": osv.get("published"),
    }


def _parse_nvd(nvd: dict) -> dict | None:
    vulns = nvd.get("vulnerabilities") or []
    if not vulns:
        return None
    cve = vulns[0].get("cve") or {}
    desc = next((d["value"] for d in cve.get("descriptions", [])
                 if d.get("lang") == "en"), "")
    sev = []
    metrics = cve.get("metrics") or {}
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        for m in metrics.get(key) or []:
            d = m.get("cvssData") or {}
            score = d.get("baseScore")
            label = d.get("baseSeverity") or m.get("baseSeverity") or ""
            sev.append(f"CVSS {d.get('version', '')}: {score} {label} "
                       f"({d.get('vectorString', '')})".strip())
        if sev:
            sev = list(dict.fromkeys(sev))   # NVD repeats CNA + NVD metrics
            break
    cwes = []
    for w in cve.get("weaknesses") or []:
        for d in w.get("description") or []:
            if d.get("value", "").startswith("CWE-"):
                cwes.append(d["value"])
    return {
        "id": cve.get("id"),
        "aliases": [],
        "summary": "",
        "details": _clip(desc),
        "severity": sev,
        "cwe_ids": list(dict.fromkeys(cwes)),
        "affected": [],
        "fixed_versions": [],
        "references": [r.get("url") for r in (cve.get("references") or []) if r.get("url")],
        "published": cve.get("published"),
    }


def _osv(vid: str) -> dict | None:
    return _http_json(f"https://api.osv.dev/v1/vulns/{vid}")


def _nvd(vid: str) -> dict | None:
    """NVD CVE record, with one retry — the keyless endpoint is rate-limited (5/30s)."""
    import time
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={vid}"
    data = _http_json(url)
    if data is None:
        time.sleep(6)
        data = _http_json(url)
    return data


def _merge_osv_facts(info: dict, o: dict) -> None:
    """Layer an OSV record's version/CWE/reference facts onto `info` (kept if richer)."""
    if o.get("affected"):
        info["affected"] = o["affected"]
    if o.get("fixed_versions"):
        info["fixed_versions"] = o["fixed_versions"]
    if o.get("aliases"):
        info["aliases"] = list(dict.fromkeys(info.get("aliases", []) + o["aliases"]))
    info["cwe_ids"] = list(dict.fromkeys(info.get("cwe_ids", []) + o["cwe_ids"]))
    info["references"] = list(dict.fromkeys(info.get("references", []) + o["references"]))
    if not info.get("summary"):
        info["summary"] = o.get("summary", "")
    if not info.get("details"):
        info["details"] = o.get("details", "")


def _fetch_advisory(vid: str) -> dict | None:
    """CVE/GHSA → curated advisory dict.

    GHSA: straight from OSV (carries ecosystem version ranges + CWE).
    CVE:  NVD for description/CVSS/CWE, enriched with version facts from OSV — preferring
          the CVE's aliased GHSA record (ecosystem ranges → real fixed versions) over the
          bare OSV CVE record (often only a GIT range). Degrades to whatever is reachable
          but returns None only if every source fails."""
    if vid.startswith("GHSA-"):
        osv = _osv(vid)
        if not osv:
            return None
        info = _parse_osv(osv)
        info["kind"] = "advisory"
        return info

    # CVE-…
    osv_cve = _osv(vid)
    ghsa_alias = next((a for a in (osv_cve or {}).get("aliases", [])
                       if a.startswith("GHSA-")), None)
    osv_rich = (_osv(ghsa_alias) if ghsa_alias else None) or osv_cve

    nvd = _nvd(vid)
    info = _parse_nvd(nvd) if nvd else None
    if info is None and osv_rich is None:
        return None
    if info is None:                          # NVD unavailable → OSV alone
        info = _parse_osv(osv_rich)
    elif osv_rich:                            # enrich NVD with OSV version/CWE facts
        _merge_osv_facts(info, _parse_osv(osv_rich))
    info["kind"] = "advisory"
    return info


def _fetch_cwe(num: str) -> dict | None:
    data = _http_json(f"https://cwe-api.mitre.org/api/v1/cwe/weakness/{num}")
    weaknesses = (data or {}).get("Weaknesses") or []
    if not weaknesses:
        return None
    w = weaknesses[0]
    cons = []
    for c in w.get("CommonConsequences") or []:
        scopes = ", ".join(c.get("Scope") or [])
        impacts = ", ".join(c.get("Impact") or [])
        cons.append(f"{scopes}: {impacts}".strip(": "))
    mits = [_clip(m.get("Description", ""), 400)
            for m in (w.get("PotentialMitigations") or [])]
    related = []
    for r in w.get("RelatedWeaknesses") or []:
        related.append(f"{r.get('Nature', '')} CWE-{r.get('CweID', '')}".strip())
    return {
        "kind": "cwe",
        "id": f"CWE-{w.get('ID', num)}",
        "name": w.get("Name", ""),
        "description": _clip(w.get("Description", ""), 800),
        "extended": _clip(w.get("ExtendedDescription", "")),
        "consequences": [c for c in cons if c],
        "mitigations": [m for m in mits if m],
        "related": related,
    }


def _format_vuln(info: dict) -> str:
    if info.get("kind") == "cwe":
        lines = [f"{info['id']}: {info['name']}", "", info["description"]]
        if info.get("extended"):
            lines += ["", info["extended"]]
        if info.get("consequences"):
            lines += ["", "Consequences:"] + [f"  - {c}" for c in info["consequences"]]
        if info.get("mitigations"):
            lines += ["", "Mitigations:"] + [f"  - {m}" for m in info["mitigations"]]
        if info.get("related"):
            lines += ["", "Related: " + "; ".join(info["related"])]
        return "\n".join(lines)
    # advisory
    lines = [info["id"] or ""]
    aliases = [a for a in (info.get("aliases") or []) if a != info.get("id")]
    if aliases:
        lines.append("aliases: " + ", ".join(aliases))
    if info.get("published"):
        lines.append(f"published: {str(info['published'])[:10]}")
    if info.get("severity"):
        lines.append("severity: " + " | ".join(info["severity"]))
    if info.get("cwe_ids"):
        lines.append("CWE: " + ", ".join(info["cwe_ids"]))
    if info.get("summary"):
        lines += ["", info["summary"]]
    if info.get("details"):
        lines += ["", info["details"]]
    if info.get("affected"):
        lines += ["", "Affected:"] + [f"  - {a}" for a in info["affected"]]
    if info.get("fixed_versions"):
        lines += ["", "Fixed versions: " + ", ".join(info["fixed_versions"])]
    if info.get("references"):
        lines += ["", "References:"] + [f"  - {u}" for u in info["references"]]
    return "\n".join(lines)


_VULN_ID_RE = re.compile(
    r"(CVE-\d{4}-\d+|GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}|CWE-?\d+)", re.I)


def _normalize_vid(id: str) -> str | None:
    vid = (id or "").strip().upper()
    if not _VULN_ID_RE.fullmatch(vid):
        return None
    if vid.startswith("CWE"):
        return "CWE-" + str(int(re.sub(r"\D", "", vid)))   # canonical, no leading zeros
    if vid.startswith("GHSA-"):
        return "GHSA-" + vid[5:].lower()      # OSV GHSA ids carry a lowercase suffix
    return vid


def _cached_info(vid: str) -> dict | None:
    cache = VULN_CACHE / f"{vid}.json"
    if cache.is_file():
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    return None


def resolve_vuln(id: str) -> str:
    """Normalize → disk-cache → fetch → format. Lazy/on-demand: an id is fetched from the
    API the first time it is looked up, the curated record is saved to
    harness/cache/vuln/<id>.json, and every later lookup (this run or any future run) is
    served from that file — no second API call."""
    vid = _normalize_vid(id)
    if vid is None:
        return ("ERROR: pass a CVE (CVE-2023-45857), GHSA (GHSA-xxxx-xxxx-xxxx) "
                "or CWE (CWE-79) id")
    info = _cached_info(vid)
    if info is None:
        info = (_fetch_cwe(re.sub(r"\D", "", vid)) if vid.startswith("CWE")
                else _fetch_advisory(vid))
        if info is None:
            return f"ERROR: {vid} not found (no record from the advisory/CWE sources)"
        try:
            VULN_CACHE.mkdir(parents=True, exist_ok=True)
            (VULN_CACHE / f"{vid}.json").write_text(
                json.dumps(info, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    return _format_vuln(info)


class ToolBox:
    """Executes tool calls against a Snapshot; records per-tool call counts."""

    def __init__(self, snap: Snapshot, groups: set[str], web: bool = False):
        self.snap = snap
        self.groups = groups
        self.web = web          # optional live-internet group (not an artifact group)
        self.calls: list[dict] = []

    # ---- code group -------------------------------------------------------

    def _safe_path(self, rel: str) -> Path | None:
        root = self.snap.worktree.resolve()
        p = (root / rel).resolve()
        return p if str(p).startswith(str(root)) else None

    def read_file(self, path: str, start_line: int = 1, end_line: int = 200) -> str:
        p = self._safe_path(path)
        if p is None or not p.is_file():
            return f"ERROR: no such file in snapshot: {path}"
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            return f"ERROR: {exc}"
        start, end = max(1, int(start_line)), min(len(lines), int(end_line))
        body = "\n".join(f"{i}\t{lines[i-1]}" for i in range(start, end + 1))
        return _trunc(f"{path} (lines {start}-{end} of {len(lines)})\n{body}")

    def list_dir(self, path: str = ".") -> str:
        p = self._safe_path(path)
        if p is None or not p.is_dir():
            return f"ERROR: no such directory in snapshot: {path}"
        entries = sorted(x.name + ("/" if x.is_dir() else "") for x in p.iterdir()
                         if x.name != ".git")
        return _trunc("\n".join(entries) or "(empty)")

    def search_code(self, pattern: str, path_glob: str = "") -> str:
        args = ["grep", "-n", "-I", "--max-count=5", "-e", pattern]
        if path_glob:
            args += ["--", path_glob]
        return _trunc(_git(self.snap.worktree, *args) or "(no matches)")

    # ---- commits group ----------------------------------------------------

    def git_log(self, path: str = "", n: int = 20) -> str:
        # Offline snapshot (container): serve the host-precomputed log. It is already
        # time-capped and ordered most-recent-first; trim to n lines. Per-path filtering is
        # not available offline, so `path` is ignored when serving precomputed history.
        if self.snap.commit_log:
            lines = self.snap.commit_log.splitlines()[:min(int(n), 50)]
            return _trunc("\n".join(lines) or "(no commits)")
        args = ["log", f"--max-count={min(int(n), 50)}",
                "--date=iso", "--pretty=format:%h %ad %an %s"]
        if path:
            args += ["--", path]
        return _trunc(_git(self.snap.worktree, *args) or "(no commits)")

    def git_show(self, sha: str) -> str:
        if not re.fullmatch(r"[0-9a-fA-F]{6,40}", sha.strip()):
            return "ERROR: pass a commit SHA (6-40 hex chars)"
        sha = sha.strip()
        # Offline snapshot (container): serve from the host-precomputed patch store, keyed by
        # 12-hex short sha. A miss means the patch was not materialized (it is either outside
        # the precomputed window or — the time-cap guarantee — not an ancestor of the snapshot).
        if self.snap.commit_patches or self.snap.commit_log:
            patch = self.snap.commit_patches.get(sha[:12])
            if patch:
                return _trunc(patch)
            return (f"ERROR: commit {sha} patch not available in this offline snapshot "
                    f"(as of {self.snap.report_time})")
        # Time-cap guard: the clone contains post-report commits; only ancestors of the
        # snapshot commit are visible.
        chk = subprocess.run(["git", "merge-base", "--is-ancestor", sha, "HEAD"],
                             cwd=self.snap.worktree, capture_output=True)
        if chk.returncode != 0:
            return f"ERROR: commit {sha} not found in the repository as of {self.snap.report_time}"
        return _trunc(_git(self.snap.worktree, "show", "--stat", "--patch", sha))

    # ---- issues / prs groups ----------------------------------------------

    @staticmethod
    def _kw_search(records: list[dict], query: str, fields, top: int) -> list[dict]:
        terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
        scored = []
        for r in records:
            text = " ".join(str(f(r)) for f in fields).lower()
            score = sum(text.count(t) for t in terms)
            if score:
                scored.append((score, r))
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:top]]

    def search_issues(self, query: str, max_results: int = 10) -> str:
        hits = self._kw_search(
            self.snap.issues, query,
            [lambda r: r["title"], lambda r: r["body"][:2000],
             lambda r: " ".join(r["labels"])], int(max_results))
        if not hits:
            return "(no matching issues in the tracker as of the report date)"
        return _trunc("\n".join(
            f"#{r['number']} [{r['state']}] {r['created_at'][:10]} {r['title']}"
            f" — {r['body'][:120]!r}" for r in hits))

    def get_issue(self, number: int) -> str:
        for r in self.snap.issues:
            if r["number"] == int(number):
                parts = [f"#{r['number']} {r['title']} [{r['state']}]"
                         f" created {r['created_at']} labels={r['labels']}",
                         r["body"], ""]
                for c in r["comments"]:
                    parts.append(f"--- {c.get('author')} at {c.get('created_at')} ---\n"
                                 f"{c.get('body', '')}")
                return _trunc("\n".join(parts))
        return f"ERROR: issue #{number} not found (as of {self.snap.report_time})"

    def search_prs(self, query: str, max_results: int = 10) -> str:
        hits = self._kw_search(
            self.snap.prs, query,
            [lambda r: r["title"], lambda r: r["body"][:2000]], int(max_results))
        if not hits:
            return "(no matching pull requests as of the report date)"
        return _trunc("\n".join(
            f"#{r['number']} [{r['outcome'] or 'open'}] {r['created_at'][:10]}"
            f"{' merged ' + r['merged_at'][:10] if r['merged_at'] else ''} {r['title']}"
            for r in hits))

    def get_pr(self, number: int) -> str:
        for r in self.snap.prs:
            if r["number"] == int(number):
                parts = [f"PR #{r['number']} {r['title']} [{r['outcome'] or 'open'}]"
                         f" created {r['created_at']} merged={r['merged_at']}",
                         r["body"]]
                for rev in r["reviews"][:10]:
                    parts.append(f"review by {rev.get('author')}: {rev.get('state')}"
                                 f" — {str(rev.get('body', ''))[:300]}")
                return _trunc("\n".join(parts))
        return f"ERROR: PR #{number} not found (as of {self.snap.report_time})"

    # ---- advisory group ----------------------------------------------------

    def search_advisories(self, query: str, max_results: int = 10) -> str:
        hits = self._kw_search(
            self.snap.advisories, query,
            [lambda r: r["id"], lambda r: " ".join(r["aliases"]),
             lambda r: r["summary"], lambda r: r["details"][:2000]], int(max_results))
        if not hits:
            return "(no matching advisories published before the report date)"
        return _trunc("\n".join(
            f"{r['id']} ({', '.join(r['aliases'])}) [{r['severity']}]"
            f" published {str(r['published'])[:10]} — {r['summary'][:140]}" for r in hits))

    def get_advisory(self, advisory_id: str) -> str:
        aid = advisory_id.strip().upper()
        for r in self.snap.advisories:
            if r["id"].upper() == aid or aid in [a.upper() for a in r["aliases"]]:
                return _trunc(
                    f"{r['id']} aliases={r['aliases']} cwe={r.get('cwe_ids') or []}"
                    f" severity={r['severity']}"
                    f" published={r['published']}\n\n{r['summary']}\n\n{r['details']}\n\n"
                    f"affected: {r['affected']}\nreferences: {r['references']}")
        return f"ERROR: advisory {advisory_id} not found (as of {self.snap.report_time})"

    def vuln_lookup(self, id: str) -> str:
        """Resolve a CVE / GHSA / CWE id to its canonical record. No time-cap gate; not
        truncated to MAX_RESULT_CHARS (a single record is bounded — only long prose
        fields are clipped). Cached on disk by id (resolve_vuln) for reproducibility."""
        return resolve_vuln(id)

    # ---- web group (optional live internet — breaks the time-cap) ----------

    def web_search(self, query: str, max_results: int = 5) -> str:
        try:
            from ddgs import DDGS
        except ImportError:
            return "ERROR: web search unavailable (the `ddgs` package is not installed)"
        try:
            hits = list(DDGS().text(query, max_results=min(int(max_results), 10)))
        except Exception as exc:
            return f"ERROR: web search failed: {exc}"
        if not hits:
            return "(no web results)"
        blocks = []
        for i, h in enumerate(hits, 1):
            blocks.append(
                f"[{i}] {h.get('title', '(untitled)')}\n"
                f"URL: {h.get('href', '')}\n"
                f"{(h.get('body') or '').strip()}")
        header = (f"{len(blocks)} web result(s) for {query!r}. "
                  "Pass any URL above to web_fetch to read the full page.\n")
        return _trunc(header + "\n\n".join(blocks))

    def web_fetch(self, url: str) -> str:
        url = url.strip()
        if not re.match(r"https?://", url):
            return "ERROR: pass an http(s) URL"
        try:
            import requests
            resp = requests.get(
                url, timeout=20, allow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; SecDevQA-agent)"})
        except Exception as exc:
            return f"ERROR: fetch failed: {exc}"
        if resp.status_code != 200:
            return f"ERROR: HTTP {resp.status_code} for {url}"
        return _trunc(f"{url} (HTTP 200)\n\n{_html_to_text(resp.text)}")

    # ---- dispatch -----------------------------------------------------------

    GROUP_OF_TOOL = {
        "read_file": "code", "list_dir": "code", "search_code": "code",
        "git_log": "commits", "git_show": "commits",
        "search_issues": "issues", "get_issue": "issues",
        "search_prs": "prs", "get_pr": "prs",
        "search_advisories": "advisory", "get_advisory": "advisory",
        "vuln_lookup": "advisory",
        "web_search": "web", "web_fetch": "web",
    }

    def execute(self, name: str, args: dict) -> str:
        group = self.GROUP_OF_TOOL.get(name)
        # The web group is gated by self.web; every other group by membership in
        # self.groups (the artifact-provision selection).
        available = self.web if group == "web" else (group in self.groups)
        if group is None or not available:
            result = f"ERROR: tool {name} is not available in this condition"
        else:
            try:
                result = getattr(self, name)(**args)
            except TypeError as exc:
                result = f"ERROR: bad arguments for {name}: {exc}"
            except Exception as exc:  # tool errors must not kill the run
                result = f"ERROR: {exc}"
        self.calls.append({"tool": name, "group": group, "args": args,
                           "result_chars": len(result)})
        return result


# ---------------------------------------------------------------------------
# OpenAI-style tool schemas (LiteLLM-compatible), emitted only for active groups
# ---------------------------------------------------------------------------

def _schema(name: str, desc: str, props: dict, required: list[str]) -> dict:
    return {"type": "function",
            "function": {"name": name, "description": desc,
                         "parameters": {"type": "object", "properties": props,
                                        "required": required}}}


_S = {"type": "string"}
_I = {"type": "integer"}

TOOL_SCHEMAS = {
    "code": [
        _schema("list_dir", "List a directory of the repository snapshot.",
                {"path": _S}, []),
        _schema("read_file", "Read a file from the repository snapshot (line-numbered).",
                {"path": _S, "start_line": _I, "end_line": _I}, ["path"]),
        _schema("search_code", "Search tracked files for a regex (git grep).",
                {"pattern": _S, "path_glob": _S}, ["pattern"]),
    ],
    "commits": [
        _schema("git_log", "Commit history (most recent first), optionally for a path.",
                {"path": _S, "n": _I}, []),
        _schema("git_show", "Show one commit's message, stat and patch by SHA.",
                {"sha": _S}, ["sha"]),
    ],
    "issues": [
        _schema("search_issues", "Keyword-search the project's issue tracker.",
                {"query": _S, "max_results": _I}, ["query"]),
        _schema("get_issue", "Read a full issue thread by number.",
                {"number": _I}, ["number"]),
    ],
    "prs": [
        _schema("search_prs", "Keyword-search the project's pull requests.",
                {"query": _S, "max_results": _I}, ["query"]),
        _schema("get_pr", "Read a pull request (body + reviews) by number.",
                {"number": _I}, ["number"]),
    ],
    "advisory": [
        _schema("search_advisories",
                "Keyword-search GitHub security advisories for this project.",
                {"query": _S, "max_results": _I}, ["query"]),
        _schema("get_advisory", "Read a full advisory by GHSA/CVE id.",
                {"advisory_id": _S}, ["advisory_id"]),
        _schema("vuln_lookup",
                "Look up the canonical record for a CVE, GHSA or CWE id "
                "(e.g. CVE-2023-45857, GHSA-wf5p-g6vw-rhxx, CWE-79). Returns severity/"
                "CVSS, affected and fixed versions, CWE mapping, references for "
                "advisories; name, description, consequences and mitigations for a CWE.",
                {"id": _S}, ["id"]),
    ],
    # Optional, gated by ToolBox.web — not one of ALL_GROUPS.
    "web": [
        _schema("web_search",
                "Search the live public internet (DuckDuckGo) and return ranked result "
                "titles, URLs and snippets. Live results may post-date the snapshot.",
                {"query": _S, "max_results": _I}, ["query"]),
        _schema("web_fetch",
                "Fetch a public web page by URL and return its readable text content.",
                {"url": _S}, ["url"]),
    ],
}


def schemas_for(groups: set[str], web: bool = False) -> list[dict]:
    out = []
    for g in ALL_GROUPS:
        if g in groups:
            out.extend(TOOL_SCHEMAS[g])
    if web:
        out.extend(TOOL_SCHEMAS["web"])
    return out
