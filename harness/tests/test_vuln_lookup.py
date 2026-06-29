"""
Verification script for the vuln_lookup tool (harness/tools.py).

Checks four things:
  1. id parsing / dispatch / normalization (offline, no network)
  2. live resolution of a CVE, a GHSA and a CWE — that the IMPORTANT fields land
     (severity/CVSS, CWE mapping, fixed versions, consequences, …)
  3. on-demand caching: an id is fetched once, then served from disk with NO further API
     call (proven by disabling the network and re-looking-up)
  4. error / not-found behavior — and that failures are NOT cached

Run it directly (human-readable PASS/FAIL, sets exit code):
    /local/home/amamun/envs/devqa/bin/python harness/tests/test_vuln_lookup.py

Or under pytest:
    /local/home/amamun/envs/devqa/bin/python -m pytest harness/tests/test_vuln_lookup.py -v

Live checks hit OSV.dev / NVD / MITRE. With no network they are skipped (not failed),
so the offline checks still verify the parsing/cache/error logic.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # repo root on path

import harness.snapshot.tools as T
from harness.snapshot.tools import ToolBox


# --- a ToolBox with the advisory group, writing to a throwaway cache dir ---------
def _box(cache_dir: Path) -> ToolBox:
    T.VULN_CACHE = cache_dir                      # redirect cache off the real one
    return ToolBox(snap=None, groups={"advisory"}, web=False)


def _lookup(box: ToolBox, vid: str) -> str:
    return box.execute("vuln_lookup", {"id": vid})


def _online() -> bool:
    """True if the canonical sources are reachable (one cheap probe)."""
    return T._http_json("https://api.osv.dev/v1/vulns/GHSA-wf5p-g6vw-rhxx") is not None


# ---------------------------------------------------------------------------
# 1. Parsing / dispatch / normalization — pure, no network
# ---------------------------------------------------------------------------

def test_normalization_and_dispatch():
    assert T._normalize_vid("cve-2023-45857") == "CVE-2023-45857"
    assert T._normalize_vid("GHSA-WF5P-G6VW-RHXX") == "GHSA-wf5p-g6vw-rhxx"  # suffix lc
    assert T._normalize_vid("CWE-0079") == "CWE-79"
    assert T._normalize_vid("CWE79") == "CWE-79"
    assert T._normalize_vid("not-an-id") is None
    assert T._normalize_vid("") is None


def test_invalid_id_is_rejected_without_network():
    with tempfile.TemporaryDirectory() as d:
        box = _box(Path(d))
        # break the network so a parse-reject can't accidentally call out
        orig, T._http_json = T._http_json, lambda *a, **k: 1 / 0
        try:
            out = _lookup(box, "garbage")
        finally:
            T._http_json = orig
        assert out.startswith("ERROR:") and "CVE" in out
        # the call is still recorded for RQ4 attribution, under the advisory group
        assert box.calls[-1]["tool"] == "vuln_lookup"
        assert box.calls[-1]["group"] == "advisory"


# ---------------------------------------------------------------------------
# 2. Live resolution — the important fields must be present
# ---------------------------------------------------------------------------

def test_cve_fields():
    if not _online():
        print("  SKIP (offline): test_cve_fields"); return
    with tempfile.TemporaryDirectory() as d:
        out = _lookup(_box(Path(d)), "CVE-2023-45857")    # axios CSRF token disclosure
        assert out.startswith("CVE-2023-45857")
        assert "CVSS" in out                              # severity
        assert "CWE-352" in out                           # weakness mapping
        assert "1.6.0" in out                             # fixed version (via OSV/GHSA)
        assert "References:" in out
        assert "aliases: CVE-2023-45857" not in out       # self-id filtered out
        assert "[truncated," not in out                   # NOT globally truncated


def test_ghsa_fields():
    if not _online():
        print("  SKIP (offline): test_ghsa_fields"); return
    with tempfile.TemporaryDirectory() as d:
        out = _lookup(_box(Path(d)), "GHSA-wf5p-g6vw-rhxx")
        assert out.startswith("GHSA-wf5p-g6vw-rhxx")
        assert "CVE-2023-45857" in out                    # the aliased CVE
        assert "Fixed versions:" in out
        assert "CWE-" in out


def test_cwe_fields():
    if not _online():
        print("  SKIP (offline): test_cwe_fields"); return
    with tempfile.TemporaryDirectory() as d:
        out = _lookup(_box(Path(d)), "CWE-79")
        assert out.startswith("CWE-79:")
        assert "Cross-site Scripting" in out
        assert "Consequences:" in out
        assert "Mitigations:" in out


# ---------------------------------------------------------------------------
# 3. On-demand caching: fetch once, then served from disk with no network
# ---------------------------------------------------------------------------

def test_cache_fetch_once_then_offline():
    if not _online():
        print("  SKIP (offline): test_cache_fetch_once_then_offline"); return
    with tempfile.TemporaryDirectory() as d:
        cache = Path(d)
        box = _box(cache)
        first = _lookup(box, "CWE-79")
        assert (cache / "CWE-79.json").is_file()          # saved on first lookup

        # Now make ANY network call explode; a cached lookup must still succeed.
        orig, T._http_json = T._http_json, lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("network called for a cached id!"))
        try:
            second = _lookup(box, "CWE-79")
        finally:
            T._http_json = orig
        assert second == first                            # identical, from disk


# ---------------------------------------------------------------------------
# 4. Not-found behavior — error returned, and NOT cached
# ---------------------------------------------------------------------------

def test_not_found_is_not_cached():
    if not _online():
        print("  SKIP (offline): test_not_found_is_not_cached"); return
    with tempfile.TemporaryDirectory() as d:
        cache = Path(d)
        out = _lookup(_box(cache), "CVE-2099-99999")      # reserved-range, unpublished
        assert out.startswith("ERROR:") and "not found" in out
        assert not (cache / "CVE-2099-99999.json").exists()   # failures aren't cached


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

def _main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print(f"vuln_lookup verification — {len(tests)} checks "
          f"({'ONLINE' if _online() else 'OFFLINE — live checks skipped'})\n")
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
        except Exception as e:                            # unexpected, surface it
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_main())
