#!/usr/bin/env python3
"""FastAPI review UI — three separate pipelines + benchmark browser.

/          → F&M classified pairs   (natural_qa_pairs_dual_stage.jsonl)
/open      → Open-coded pairs       (open_qa_pairs.jsonl)
/security  → Security QA pairs      (security_qa_pairs.jsonl)
/benchmark → Security benchmark     (dataset/security_benchmark.jsonl)
/normalized→ Normalized eval QA pairs (dataset/eval_pairs.jsonl)
"""

import json
import re
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Optional, Union

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output"

# ── F&M pipeline files ────────────────────────────────────────────────────────
VERIFICATION_FILE = ROOT / "verified_state.json"
EXPORT_FILE = ROOT / "verified_qa_pairs.jsonl"

# ── Open-coding pipeline files ────────────────────────────────────────────────
OPEN_VERIFICATION_FILE = ROOT / "open_verified_state.json"
OPEN_EXPORT_FILE = ROOT / "open_verified_qa_pairs.jsonl"

# ── Security QA pipeline files ─────────────────────────────────────────────────
SECURITY_VERIFICATION_FILE = ROOT / "security_verified_state.json"
SECURITY_EXPORT_FILE = ROOT / "security_verified_qa_pairs.jsonl"

# ── Benchmark dataset files ────────────────────────────────────────────────────
BENCHMARK_FILE = ROOT / "dataset" / "security_benchmark.jsonl"
# Public benchmark browser reads the *final* artifact (includes normalized
# qa_pairs); falls back to the legacy file if the final one is absent.
BENCHMARK_FINAL_FILE = ROOT / "dataset" / "security_benchmark_final.jsonl"

# Per-item grading rubrics (build_rubrics.py output) + human verification state.
RUBRICS_DRAFT_FILE = ROOT / "dataset" / "rubrics_draft.jsonl"
RUBRICS_VERIFIED_FILE = ROOT / "dataset" / "rubrics_verified.json"


def benchmark_path() -> Path:
    return BENCHMARK_FINAL_FILE if BENCHMARK_FINAL_FILE.exists() else BENCHMARK_FILE

# ── Open-coding review files ───────────────────────────────────────────────────
OC_CODES_FILE = ROOT / "dataset" / "open_codes.jsonl"
OC_VERIFIED_FILE = ROOT / "dataset" / "open_codes_verified.json"
OC_EXPORT_FILE = ROOT / "dataset" / "open_codes_verified.jsonl"

# ── Normalized eval-pairs review files ──────────────────────────────────────────
# Stage-1 normalizer output (dataset/synthesize.py). Reviewed in place: `approved` /
# `review_status` are written back into this file (the pipeline reads `approved`).
EVAL_PAIRS_FILE = ROOT / "dataset" / "eval_pairs.jsonl"
# Source threads (with full comments[]) joined in for side-by-side review.
EVAL_SOURCE_FILES = [
    ROOT / "dataset" / "security_benchmark_filtered.jsonl",
    ROOT / "dataset" / "security_benchmark.jsonl",
]

sys.path.insert(0, str(ROOT / "pipeline"))
from utils.taxonomy import CATEGORIES, QUESTIONS, QUESTION_TO_CATEGORY  # noqa: E402


# ── F&M pipeline data ─────────────────────────────────────────────────────────

pairs: list[dict] = []
verification: dict[str, dict] = {}


def pair_id(p: dict) -> str:
    return "{}/{}/{}/{}".format(
        p.get("repo", "unknown"),
        p.get("source", "unknown"),
        p.get("number", "unknown"),
        p.get("question_id", "unknown"),
    )


def load_data() -> None:
    global pairs, verification
    pairs = []
    for jsonl_file in sorted(OUTPUT_DIR.glob("*/natural_qa_pairs_dual_stage.jsonl")):
        with jsonl_file.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    pairs.append(json.loads(line))

    if VERIFICATION_FILE.exists():
        verification = json.loads(VERIFICATION_FILE.read_text(encoding="utf-8"))
    else:
        verification = {}

    # Migrate legacy integer-index keys to pair_id keys
    if any(k.isdigit() for k in verification):
        migrated = {}
        for k, v in verification.items():
            if k.isdigit():
                idx = int(k)
                if 0 <= idx < len(pairs):
                    migrated[pair_id(pairs[idx])] = v
            else:
                migrated[k] = v
        verification = migrated
        save_verification()


def save_verification() -> None:
    VERIFICATION_FILE.write_text(json.dumps(verification, indent=2))


# ── Open-coding pipeline data ─────────────────────────────────────────────────

open_pairs: list[dict] = []
open_verification: dict[str, dict] = {}


def open_pair_id(p: dict) -> str:
    return "{}/{}/{}".format(
        p.get("repo", "unknown"),
        p.get("source", "unknown"),
        p.get("number", "unknown"),
    )


def load_open_data() -> None:
    global open_pairs, open_verification
    open_pairs = []
    for jsonl_file in sorted(OUTPUT_DIR.glob("*/open_qa_pairs.jsonl")):
        with jsonl_file.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    open_pairs.append(json.loads(line))

    if OPEN_VERIFICATION_FILE.exists():
        open_verification = json.loads(OPEN_VERIFICATION_FILE.read_text(encoding="utf-8"))
    else:
        open_verification = {}


def save_open_verification() -> None:
    OPEN_VERIFICATION_FILE.write_text(json.dumps(open_verification, indent=2))


# ── Security QA pipeline data ──────────────────────────────────────────────────

security_pairs: list[dict] = []
security_verification: dict[str, dict] = {}


def security_pair_id(p: dict) -> str:
    return "{}/{}/{}".format(
        p.get("repo", "unknown"),
        p.get("source", "unknown"),
        p.get("number", "unknown"),
    )


def _security_chat_id(p: dict) -> str:
    repo = (p.get("repo") or "unknown").replace("/", "__")
    return f"{repo}__{p.get('source', 'unknown')}__{p.get('number', 'unknown')}"


def _find_by_chat_id(chat_id: str):
    for i, p in enumerate(security_pairs):
        if _security_chat_id(p) == chat_id:
            return i, p
    return None, None


def load_security_data() -> None:
    global security_pairs, security_verification
    security_pairs = []
    for jsonl_file in sorted(OUTPUT_DIR.glob("*/security_qa_pairs.jsonl")):
        with jsonl_file.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    security_pairs.append(json.loads(line))

    if SECURITY_VERIFICATION_FILE.exists():
        security_verification = json.loads(SECURITY_VERIFICATION_FILE.read_text(encoding="utf-8"))
    else:
        security_verification = {}


def save_security_verification() -> None:
    SECURITY_VERIFICATION_FILE.write_text(json.dumps(security_verification, indent=2))


# ── Models ────────────────────────────────────────────────────────────────────


class VerifyRequest(BaseModel):
    status: str  # "accepted" | "rejected" | "pending"
    note: Optional[str] = ""


class AssignRequest(BaseModel):
    question_id: str


class ChatMessage(BaseModel):
    role: str   # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: Optional[str] = None


class BenchmarkEditRequest(BaseModel):
    qa_summary: Optional[str] = None
    security_topic: Optional[str] = None
    human_note: Optional[str] = None
    question_comment_id: Optional[str] = None
    answer_comment_id: Optional[str] = None
    answerer_role: Optional[str] = None
    resolution_case: Optional[str] = None
    artifacts_needed: Optional[list[str]] = None
    hard_facts: Optional[dict] = None
    # This is the final manual-checking stage, so any field can be edited:
    # `qa_pairs` replaces the normalized Q&A list; `full` overwrites the whole
    # record; `fields` patches arbitrary top-level keys.
    qa_pairs: Optional[list[dict]] = None
    fields: Optional[dict] = None
    full: Optional[dict] = None


# Keys the editor injects into a record for display — never persisted back.
_TRANSIENT_KEYS = ("index", "rubrics")


class RubricSaveRequest(BaseModel):
    qid: str
    status: Optional[str] = None            # accepted | edited | rejected
    rubric: Optional[list] = None           # full edited line list
    acceptable_alternatives: Optional[Union[str, list]] = None
    note: Optional[str] = None


class OCSaveRequest(BaseModel):
    status: str           # "accepted" | "rejected" | "pending"
    codes: list[str]      # edited codes list
    rationale: Optional[str] = ""
    note: Optional[str] = ""


class NormQAPair(BaseModel):
    qid: Optional[str] = None
    question: str
    answer: str
    knowledge_type: str                       # "parametric" | "grounded"
    grounding_sources: list[str] = []
    answer_grounded_in: Optional[str] = None


class NormSaveRequest(BaseModel):
    status: str                               # "approved" | "rejected" | "pending"
    qa_pairs: list[NormQAPair]
    note: Optional[str] = ""


# ── Open-coding data ───────────────────────────────────────────────────────────

oc_records: list[dict] = []          # merged: LLM codes + benchmark context
oc_verified: dict[str, dict] = {}    # keyed by record id string


def load_oc_data() -> None:
    global oc_records, oc_verified
    oc_records = []

    # Index benchmark by id for fast join
    bm_by_id: dict[str, dict] = {}
    if BENCHMARK_FILE.exists():
        with BENCHMARK_FILE.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    bm_by_id[r["id"]] = r

    if OC_CODES_FILE.exists():
        with OC_CODES_FILE.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                oc = json.loads(line)
                bm = bm_by_id.get(oc["id"], {})
                oc_records.append({**bm, **oc})   # bm first, oc fields win

    if OC_VERIFIED_FILE.exists():
        oc_verified = json.loads(OC_VERIFIED_FILE.read_text(encoding="utf-8"))
    else:
        oc_verified = {}


def save_oc_verified() -> None:
    OC_VERIFIED_FILE.write_text(json.dumps(oc_verified, indent=2), encoding="utf-8")


# ── Benchmark data ─────────────────────────────────────────────────────────────

benchmark_records: list[dict] = []


def load_benchmark_data() -> None:
    global benchmark_records
    benchmark_records = []
    path = benchmark_path()
    if path.exists():
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    benchmark_records.append(json.loads(line))


def save_benchmark_data() -> None:
    path = benchmark_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in benchmark_records:
            f.write(json.dumps(record) + "\n")


# ── Grading rubric drafts + verification ────────────────────────────────────────

rubrics_by_qid: dict[str, dict] = {}     # qid -> draft rubric (build_rubrics.py output)
rubrics_verified: dict[str, dict] = {}   # qid -> human-edited overlay {status, rubric, ...}


def load_rubrics_data() -> None:
    global rubrics_by_qid, rubrics_verified
    rubrics_by_qid = {}
    if RUBRICS_DRAFT_FILE.exists():
        with RUBRICS_DRAFT_FILE.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    if r.get("qid"):
                        rubrics_by_qid[r["qid"]] = r
    rubrics_verified = {}
    if RUBRICS_VERIFIED_FILE.exists():
        rubrics_verified = json.loads(RUBRICS_VERIFIED_FILE.read_text(encoding="utf-8"))


def save_rubrics_verified() -> None:
    RUBRICS_VERIFIED_FILE.write_text(json.dumps(rubrics_verified, indent=2), encoding="utf-8")


def merged_rubric(qid: str, overlay: Optional[dict] = None) -> Optional[dict]:
    """Draft rubric with a verification overlay applied (edits win). When `overlay`
    is given (a per-reviewer rubric dict) it is used instead of the shared author
    overlay `rubrics_verified` — so reviewers rate independently."""
    draft = rubrics_by_qid.get(qid)
    ver = overlay if overlay is not None else rubrics_verified.get(qid)
    if draft is None and ver is None:
        return None
    base = dict(draft or {"qid": qid, "rubric": []})
    base["verify_status"] = "draft"
    if ver:
        for k in ("rubric", "acceptable_alternatives", "note"):
            if ver.get(k) is not None:
                base[k] = ver[k]
        base["verify_status"] = ver.get("status", "edited")
    return base


# ── Per-reviewer overlays (inter-rater review on /benchmark) ─────────────────────
# When a request carries ?reviewer=<id>, benchmark edits + rubric edits are written to
# that reviewer's OWN file, dataset/reviews/<id>.json, instead of mutating the shared
# source-of-truth files. Each file is keyed by record id; every entry carries the
# reviewer's edited fields AND rubrics (per qid) + the reviewer name + reviewed_at — so
# one file fully holds that reviewer's work. agreement.py reads dataset/reviews/*.json.
REVIEWS_DIR = ROOT / "dataset" / "reviews"
_REVIEWER_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_OVERLAY_FIELDS = ("qa_summary", "security_topic", "human_note", "question_comment_id",
                   "answer_comment_id", "answerer_role", "resolution_case",
                   "artifacts_needed", "hard_facts", "qa_pairs")


def valid_reviewer(reviewer: Optional[str]) -> Optional[str]:
    if reviewer is None:
        return None
    if not _REVIEWER_RE.match(reviewer):
        raise HTTPException(400, "reviewer must match [A-Za-z0-9_-]{1,32}, e.g. R1")
    return reviewer


def load_reviews(reviewer: str) -> dict:
    """This reviewer's file (record_id -> entry). Empty dict if not started yet."""
    p = REVIEWS_DIR / f"{reviewer}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_reviews(reviewer: str, data: dict) -> None:
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    (REVIEWS_DIR / f"{reviewer}.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def apply_overlay_fields(record: dict, entry: dict) -> dict:
    """Return a copy of a benchmark record with a reviewer's saved field edits applied."""
    r = dict(record)
    for k, v in (entry.get("fields") or {}).items():
        if k == "hard_facts":
            hf = dict(r.get("hard_facts") or {})
            hf.update(v or {})
            r["hard_facts"] = hf
        else:
            r[k] = v
    return r


# ── Normalized eval-pairs data ──────────────────────────────────────────────────

norm_records: list[dict] = []            # eval_pairs.jsonl records (in file order)
norm_source_by_id: dict[str, dict] = {}  # thread_id -> source thread (with comments)

FIX_FACT_FIELDS = ("fixed_versions", "fix_prs", "fix_commits", "advisory_urls")


def _norm_status(r: dict) -> str:
    """3-way review status derived from the record. `approved:true` -> approved;
    an explicit review_status is authoritative if present; else pending."""
    rs = r.get("review_status")
    if rs in ("approved", "rejected", "pending"):
        return rs
    return "approved" if r.get("approved") else "pending"


def _fix_leak_flags(question: str, hard_facts: dict) -> list[str]:
    """Fix-type identifiers (the resolution) appearing in the question text."""
    leaked, ql = [], (question or "").lower()
    for field in FIX_FACT_FIELDS:
        for val in (hard_facts or {}).get(field, []) or []:
            if val and str(val).lower() in ql:
                leaked.append(f"{field}:{val}")
    return leaked


def load_norm_data() -> None:
    global norm_records, norm_source_by_id
    norm_records = []
    norm_source_by_id = {}
    for src in EVAL_SOURCE_FILES:
        if not src.exists():
            continue
        with src.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                t = json.loads(line)
                norm_source_by_id.setdefault(t["id"], t)  # first file wins
    if EVAL_PAIRS_FILE.exists():
        with EVAL_PAIRS_FILE.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    norm_records.append(json.loads(line))


def save_norm_data() -> None:
    EVAL_PAIRS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with EVAL_PAIRS_FILE.open("w", encoding="utf-8") as f:
        for record in norm_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── App ───────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_data()
    load_open_data()
    load_security_data()
    load_benchmark_data()
    load_rubrics_data()
    load_oc_data()
    load_norm_data()
    print(
        f"Loaded {len(pairs)} F&M pairs, {len(open_pairs)} open-coded pairs, "
        f"{len(security_pairs)} security pairs, {len(benchmark_records)} benchmark records, "
        f"{len(oc_records)} open-coding records, {len(norm_records)} normalized threads",
        file=sys.stderr,
    )
    yield


_INDEX_HTML = Path(__file__).parent / "templates" / "index.html"
_TAXONOMY_HTML = Path(__file__).parent / "templates" / "taxonomy.html"
_STATS_HTML = Path(__file__).parent / "templates" / "stats.html"
_CHAT_HTML = Path(__file__).parent / "templates" / "chat.html"
_BENCHMARK_HTML = Path(__file__).parent / "templates" / "benchmark.html"
_OC_HTML = Path(__file__).parent / "templates" / "open_coding.html"
_NORM_HTML = Path(__file__).parent / "templates" / "normalized.html"

app = FastAPI(title="DevQA – Pair Review Tool", lifespan=lifespan)
app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)


# ── Shared pages ──────────────────────────────────────────────────────────────


@app.get("/taxonomy", response_class=HTMLResponse)
async def taxonomy_page():
    return HTMLResponse(_TAXONOMY_HTML.read_text(encoding="utf-8"))


@app.get("/api/taxonomy")
def get_taxonomy():
    return {
        "categories": {k: {"name": v[0], "qs": v[1]} for k, v in CATEGORIES.items()},
        "questions": QUESTIONS,
    }


# ══════════════════════════════════════════════════════════════════════════════
# F&M CLASSIFIED PIPELINE  (/  and  /api/*)
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(_INDEX_HTML.read_text(encoding="utf-8"))


@app.get("/stats", response_class=HTMLResponse)
async def stats_page():
    return HTMLResponse(_STATS_HTML.read_text(encoding="utf-8"))


@app.get("/api/pairs")
def get_pairs(
    repo: Optional[str] = None,
    question_id: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
):
    filtered = []
    for i, p in enumerate(pairs):
        v = verification.get(pair_id(p), {})
        vstatus = v.get("status", "pending")
        effective_qid = v.get("question_id_override", p.get("question_id"))

        if repo and p.get("repo") != repo:
            continue
        if question_id and effective_qid != question_id:
            continue
        if status and vstatus != status:
            continue
        if q:
            q_lower = q.lower()
            if (
                q_lower not in p.get("question_text", "").lower()
                and q_lower not in p.get("answer_text", "").lower()
                and q_lower not in p.get("title", "").lower()
            ):
                continue

        filtered.append({
            "index": i,
            "repo": p.get("repo"),
            "question_id": effective_qid,
            "number": p.get("number"),
            "question_text": p.get("question_text", ""),
            "title": p.get("title"),
            "confidence": p.get("confidence"),
            "stage1_category": p.get("stage1_category") or p.get("category"),
            "source": p.get("source"),
            "status": vstatus,
            "note": v.get("note", ""),
        })

    total = len(filtered)
    start = (page - 1) * page_size
    return {"total": total, "page": page, "page_size": page_size,
            "items": filtered[start: start + page_size]}


@app.get("/api/pairs/{index}")
def get_pair(index: int):
    if index < 0 or index >= len(pairs):
        raise HTTPException(status_code=404, detail="Pair not found")
    p = dict(pairs[index])
    v = verification.get(pair_id(p), {})
    p["index"] = index
    p["status"] = v.get("status", "pending")
    p["note"] = v.get("note", "")
    p["verified_at"] = v.get("verified_at", "")
    p["stage1_category"] = p.get("stage1_category") or p.get("category")
    if "question_id_override" in v:
        p["question_id"] = v["question_id_override"]
    return p


@app.post("/api/pairs/{index}/verify")
def verify_pair(index: int, body: VerifyRequest):
    if index < 0 or index >= len(pairs):
        raise HTTPException(status_code=404, detail="Pair not found")
    if body.status not in ("accepted", "rejected", "pending"):
        raise HTTPException(status_code=400, detail="Invalid status")
    verification[pair_id(pairs[index])] = {
        "status": body.status,
        "note": body.note or "",
        "verified_at": datetime.utcnow().isoformat() + "Z",
    }
    save_verification()
    return {"ok": True}


@app.post("/api/pairs/{index}/assign")
def assign_question_id(index: int, body: AssignRequest):
    if index < 0 or index >= len(pairs):
        raise HTTPException(status_code=404, detail="Pair not found")
    if body.question_id not in QUESTIONS:
        raise HTTPException(status_code=400, detail="Unknown question_id")
    entry = verification.setdefault(pair_id(pairs[index]), {"status": "pending", "note": ""})
    entry["question_id_override"] = body.question_id
    save_verification()
    return {"ok": True}


@app.get("/api/stats")
def get_stats():
    repos: dict[str, int] = {}
    question_ids: dict[str, int] = {}
    categories: dict[str, int] = {}
    cat_status: dict[str, dict[str, int]] = {}
    counts = {"accepted": 0, "rejected": 0, "pending": 0}

    for p in pairs:
        repos[p.get("repo", "unknown")] = repos.get(p.get("repo", "unknown"), 0) + 1
        v = verification.get(pair_id(p), {})
        status = v.get("status", "pending")
        counts[status] = counts.get(status, 0) + 1
        qid = v.get("question_id_override", p.get("question_id", "?"))
        question_ids[qid] = question_ids.get(qid, 0) + 1
        cat = QUESTION_TO_CATEGORY.get(qid, "?")
        categories[cat] = categories.get(cat, 0) + 1
        cs = cat_status.setdefault(cat, {"accepted": 0, "rejected": 0, "pending": 0})
        cs[status] = cs.get(status, 0) + 1

    return {
        "total": len(pairs),
        "counts": counts,
        "repos": repos,
        "question_ids": dict(sorted(question_ids.items(), key=lambda x: -x[1])),
        "categories": categories,
        "cat_status": cat_status,
    }


@app.post("/api/reload")
def reload_data():
    load_data()
    return {"ok": True, "total": len(pairs)}


@app.post("/api/export")
def export_verified():
    accepted = [p for p in pairs if verification.get(pair_id(p), {}).get("status") == "accepted"]
    with EXPORT_FILE.open("w") as f:
        for p in accepted:
            f.write(json.dumps(p) + "\n")
    return {"exported": len(accepted), "file": str(EXPORT_FILE)}


@app.get("/api/export/download")
def download_export():
    if not EXPORT_FILE.exists():
        raise HTTPException(status_code=404, detail="No export yet. Run export first.")
    return FileResponse(EXPORT_FILE, filename="verified_qa_pairs.jsonl",
                        media_type="application/octet-stream")


@app.get("/api/repos")
def get_repos():
    return sorted({p.get("repo", "") for p in pairs})


@app.get("/api/question_ids")
def get_question_ids():
    return sorted({p.get("question_id", "") for p in pairs})


# ══════════════════════════════════════════════════════════════════════════════
# OPEN-CODING PIPELINE  (/open  and  /api/open/*)
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/open", response_class=HTMLResponse)
async def open_index():
    return HTMLResponse(_INDEX_HTML.read_text(encoding="utf-8"))


@app.get("/open/stats", response_class=HTMLResponse)
async def open_stats_page():
    return HTMLResponse(_STATS_HTML.read_text(encoding="utf-8"))


@app.get("/api/open/pairs")
def get_open_pairs(
    repo: Optional[str] = None,
    status: Optional[str] = None,
    verifiability: Optional[str] = None,
    answerer_role: Optional[str] = None,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
):
    filtered = []
    for i, p in enumerate(open_pairs):
        v = open_verification.get(open_pair_id(p), {})
        vstatus = v.get("status", "pending")

        if repo and p.get("repo") != repo:
            continue
        if status and vstatus != status:
            continue
        if verifiability and p.get("verifiability") != verifiability:
            continue
        if answerer_role and p.get("answerer_role") != answerer_role:
            continue
        if q:
            q_lower = q.lower()
            if (
                q_lower not in p.get("need_summary", "").lower()
                and q_lower not in p.get("question_text", "").lower()
                and q_lower not in p.get("answer_text", "").lower()
                and q_lower not in p.get("title", "").lower()
            ):
                continue

        filtered.append({
            "index": i,
            "repo": p.get("repo"),
            "question_id": "OPEN",
            "number": p.get("number"),
            "need_summary": p.get("need_summary", ""),
            "question_text": p.get("question_text", ""),
            "title": p.get("title"),
            "confidence": p.get("confidence"),
            "verifiability": p.get("verifiability", ""),
            "answerer_role": p.get("answerer_role", ""),
            "artifacts_needed": p.get("artifacts_needed", []),
            "source": p.get("source"),
            "state": p.get("state", ""),
            "status": vstatus,
            "note": v.get("note", ""),
        })

    total = len(filtered)
    start = (page - 1) * page_size
    return {"total": total, "page": page, "page_size": page_size,
            "items": filtered[start: start + page_size]}


@app.get("/api/open/pairs/{index}")
def get_open_pair(index: int):
    if index < 0 or index >= len(open_pairs):
        raise HTTPException(status_code=404, detail="Pair not found")
    p = dict(open_pairs[index])
    v = open_verification.get(open_pair_id(p), {})
    p["index"] = index
    p["status"] = v.get("status", "pending")
    p["note"] = v.get("note", "")
    p["verified_at"] = v.get("verified_at", "")
    p["question_id"] = "OPEN"
    return p


@app.post("/api/open/pairs/{index}/verify")
def verify_open_pair(index: int, body: VerifyRequest):
    if index < 0 or index >= len(open_pairs):
        raise HTTPException(status_code=404, detail="Pair not found")
    if body.status not in ("accepted", "rejected", "pending"):
        raise HTTPException(status_code=400, detail="Invalid status")
    open_verification[open_pair_id(open_pairs[index])] = {
        "status": body.status,
        "note": body.note or "",
        "verified_at": datetime.utcnow().isoformat() + "Z",
    }
    save_open_verification()
    return {"ok": True}


@app.get("/api/open/stats")
def get_open_stats():
    repos: dict[str, int] = {}
    verif_counts: dict[str, int] = {}
    verif_status: dict[str, dict[str, int]] = {}
    role_counts: dict[str, int] = {}
    counts = {"accepted": 0, "rejected": 0, "pending": 0}

    for p in open_pairs:
        repos[p.get("repo", "unknown")] = repos.get(p.get("repo", "unknown"), 0) + 1
        v = open_verification.get(open_pair_id(p), {})
        status = v.get("status", "pending")
        counts[status] = counts.get(status, 0) + 1
        verif = p.get("verifiability", "?")
        verif_counts[verif] = verif_counts.get(verif, 0) + 1
        vs = verif_status.setdefault(verif, {"accepted": 0, "rejected": 0, "pending": 0})
        vs[status] = vs.get(status, 0) + 1
        role = p.get("answerer_role", "?")
        role_counts[role] = role_counts.get(role, 0) + 1

    return {
        "total": len(open_pairs),
        "counts": counts,
        "repos": repos,
        "question_ids": {"OPEN": len(open_pairs)},
        "categories": verif_counts,
        "cat_status": verif_status,
        "answerer_roles": role_counts,
    }


@app.post("/api/open/reload")
def reload_open_data():
    load_open_data()
    return {"ok": True, "total": len(open_pairs)}


@app.post("/api/open/export")
def export_open_verified():
    accepted = [
        p for p in open_pairs
        if open_verification.get(open_pair_id(p), {}).get("status") == "accepted"
    ]
    with OPEN_EXPORT_FILE.open("w") as f:
        for p in accepted:
            f.write(json.dumps(p) + "\n")
    return {"exported": len(accepted), "file": str(OPEN_EXPORT_FILE)}


@app.get("/api/open/export/download")
def download_open_export():
    if not OPEN_EXPORT_FILE.exists():
        raise HTTPException(status_code=404, detail="No export yet. Run export first.")
    return FileResponse(OPEN_EXPORT_FILE, filename="open_verified_qa_pairs.jsonl",
                        media_type="application/octet-stream")


@app.get("/api/open/repos")
def get_open_repos():
    return sorted({p.get("repo", "") for p in open_pairs})


@app.get("/api/open/question_ids")
def get_open_question_ids():
    return ["OPEN"]


# ══════════════════════════════════════════════════════════════════════════════
# SECURITY QA PIPELINE  (/security  and  /api/security/*)
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/security", response_class=HTMLResponse)
async def security_index():
    return HTMLResponse(_INDEX_HTML.read_text(encoding="utf-8"))


@app.get("/security/stats", response_class=HTMLResponse)
async def security_stats_page():
    return HTMLResponse(_STATS_HTML.read_text(encoding="utf-8"))


@app.get("/api/security/pairs")
def get_security_pairs(
    repo: Optional[str] = None,
    status: Optional[str] = None,
    security_topic: Optional[str] = None,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
):
    filtered = []
    for i, p in enumerate(security_pairs):
        v = security_verification.get(security_pair_id(p), {})
        vstatus = v.get("status", "pending")

        if repo and p.get("repo") != repo:
            continue
        if status and vstatus != status:
            continue
        if security_topic and p.get("security_topic") != security_topic:
            continue
        if q:
            q_lower = q.lower()
            if (
                q_lower not in p.get("need_summary", "").lower()
                and q_lower not in p.get("security_topic", "").lower()
                and q_lower not in p.get("question_text", "").lower()
                and q_lower not in p.get("answer_text", "").lower()
                and q_lower not in p.get("title", "").lower()
            ):
                continue

        filtered.append({
            "index": i,
            "chat_id": _security_chat_id(p),
            "repo": p.get("repo"),
            "question_id": "SECURITY_OPEN",
            "number": p.get("number"),
            "need_summary": p.get("need_summary", ""),
            "security_topic": p.get("security_topic", ""),
            "question_text": p.get("question_text", ""),
            "title": p.get("title"),
            "confidence": p.get("confidence"),
            "artifacts_needed": p.get("artifacts_needed", []),
            "source": p.get("source"),
            "state": p.get("state", ""),
            "status": vstatus,
            "note": v.get("note", ""),
        })

    total = len(filtered)
    start = (page - 1) * page_size
    return {"total": total, "page": page, "page_size": page_size,
            "items": filtered[start: start + page_size]}


@app.get("/api/security/pairs/{index}")
def get_security_pair(index: int):
    if index < 0 or index >= len(security_pairs):
        raise HTTPException(status_code=404, detail="Pair not found")
    p = dict(security_pairs[index])
    v = security_verification.get(security_pair_id(p), {})
    p["index"] = index
    p["chat_id"] = _security_chat_id(p)
    p["status"] = v.get("status", "pending")
    p["note"] = v.get("note", "")
    p["verified_at"] = v.get("verified_at", "")
    p["question_id"] = "SECURITY_OPEN"
    return p


@app.post("/api/security/pairs/{index}/verify")
def verify_security_pair(index: int, body: VerifyRequest):
    if index < 0 or index >= len(security_pairs):
        raise HTTPException(status_code=404, detail="Pair not found")
    if body.status not in ("accepted", "rejected", "pending"):
        raise HTTPException(status_code=400, detail="Invalid status")
    security_verification[security_pair_id(security_pairs[index])] = {
        "status": body.status,
        "note": body.note or "",
        "verified_at": datetime.utcnow().isoformat() + "Z",
    }
    save_security_verification()
    return {"ok": True}


@app.get("/api/security/stats")
def get_security_stats():
    repos: dict[str, int] = {}
    topic_counts: dict[str, int] = {}
    topic_status: dict[str, dict[str, int]] = {}
    counts = {"accepted": 0, "rejected": 0, "pending": 0}

    for p in security_pairs:
        repos[p.get("repo", "unknown")] = repos.get(p.get("repo", "unknown"), 0) + 1
        v = security_verification.get(security_pair_id(p), {})
        status = v.get("status", "pending")
        counts[status] = counts.get(status, 0) + 1
        topic = p.get("security_topic", "?") or "?"
        topic_counts[topic] = topic_counts.get(topic, 0) + 1
        ts = topic_status.setdefault(topic, {"accepted": 0, "rejected": 0, "pending": 0})
        ts[status] = ts.get(status, 0) + 1

    return {
        "total": len(security_pairs),
        "counts": counts,
        "repos": repos,
        "question_ids": {"SECURITY_OPEN": len(security_pairs)},
        "categories": topic_counts,
        "cat_status": topic_status,
    }


@app.post("/api/security/reload")
def reload_security_data():
    load_security_data()
    return {"ok": True, "total": len(security_pairs)}


@app.post("/api/security/export")
def export_security_verified():
    accepted = [
        p for p in security_pairs
        if security_verification.get(security_pair_id(p), {}).get("status") == "accepted"
    ]
    with SECURITY_EXPORT_FILE.open("w") as f:
        for p in accepted:
            f.write(json.dumps(p) + "\n")
    return {"exported": len(accepted), "file": str(SECURITY_EXPORT_FILE)}


@app.get("/api/security/export/download")
def download_security_export():
    if not SECURITY_EXPORT_FILE.exists():
        raise HTTPException(status_code=404, detail="No export yet. Run export first.")
    return FileResponse(SECURITY_EXPORT_FILE, filename="security_verified_qa_pairs.jsonl",
                        media_type="application/octet-stream")


@app.get("/api/security/repos")
def get_security_repos():
    return sorted({p.get("repo", "") for p in security_pairs})


@app.get("/api/security/question_ids")
def get_security_question_ids():
    return ["SECURITY_OPEN"]


# ══════════════════════════════════════════════════════════════════════════════
# SECURITY CHAT  (/security/chat  and  /api/security/chat/*)
# ══════════════════════════════════════════════════════════════════════════════


def _build_security_system_prompt(p: dict) -> str:
    hf = p.get("hard_facts") or {}

    def fmt_list(lst):
        return ", ".join(lst) if lst else "none"

    hard_facts_block = "\n".join([
        f"  CVE IDs:           {fmt_list(hf.get('cve_ids', []))}",
        f"  GHSA IDs:          {fmt_list(hf.get('ghsa_ids', []))}",
        f"  CWE IDs:           {fmt_list(hf.get('cwe_ids', []))}",
        f"  OSV IDs:           {fmt_list(hf.get('osv_ids', []))}",
        f"  Fixed versions:    {fmt_list(hf.get('fixed_versions', []))}",
        f"  Affected versions: {fmt_list(hf.get('affected_versions', []))}",
        f"  Fix PRs:           {fmt_list(hf.get('fix_prs', []))}",
        f"  Fix commits:       {fmt_list(hf.get('fix_commits', []))}",
        f"  Advisory URLs:     {fmt_list(hf.get('advisory_urls', []))}",
    ])

    artifacts = ", ".join(p.get("artifacts_needed") or []) or "none"
    thread_text = (p.get("thread_text") or "")[:10000]

    return f"""You are a security research assistant helping a human reviewer decide whether a Q&A pair extracted from a public GitHub issue thread is a valid, high-quality developer security information need.

== EXTRACTED PAIR ==
Repository:      {p.get("repo", "")}
Source:          {p.get("source", "")} #{p.get("number", "")}
Title:           {p.get("title", "")}
URL:             {p.get("url", "")}

Security topic:  {p.get("security_topic", "")}
Need summary:    {p.get("need_summary", "")}

QUESTION:
{p.get("question_text", "")}

ANSWER:
{p.get("answer_text", "")}

Answerer role:   {p.get("answerer_role", "")}
Artifacts needed: {artifacts}
Stage-1 confidence: {p.get("stage1_confidence", "")} ({p.get("stage1_n_yes", "?")}/{p.get("stage1_n_samples", "?")} votes)
Stage-2 confidence: {p.get("stage2_confidence", "")}

HARD FACTS:
{hard_facts_block}

Current label:   {p.get("status", "pending")}
Reviewer note:   {p.get("note", "") or "(none)"}

== ORIGINAL THREAD ==
{thread_text}

== YOUR ROLE ==
Help the reviewer decide if this pair should be accepted or rejected. Answer questions about the thread, the extracted Q&A, the hard facts, or the security topic. You may suggest a better security_topic phrase if the current one is inaccurate. Be concise and direct. When referencing comments, use their [cN] tag from the thread."""


@app.get("/security/chat", response_class=HTMLResponse)
async def security_chat_page():
    return HTMLResponse(_CHAT_HTML.read_text(encoding="utf-8"))


@app.get("/api/security/chat/models")
def get_chat_models():
    from utils.ollama_client import STAGE1_MODEL
    import urllib.request
    default = STAGE1_MODEL
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
            data = json.loads(r.read())
        names = sorted([m["name"] for m in data.get("models", [])])
        # Put the default model first regardless of sort order
        if default in names:
            names = [default] + [n for n in names if n != default]
        return {"models": names, "default": default}
    except Exception:
        return {"models": [], "default": default}


@app.get("/api/security/chat/context")
def get_security_chat_context(id: str):
    idx, p = _find_by_chat_id(id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"Pair not found: {id}")
    p = dict(p)
    v = security_verification.get(security_pair_id(p), {})
    p["status"] = v.get("status", "pending")
    p["note"] = v.get("note", "")
    p["chat_id"] = id
    p.pop("thread_text", None)
    p.pop("comments", None)
    return p


@app.post("/api/security/chat/stream")
async def security_chat_stream(id: str, body: ChatRequest):
    idx, p = _find_by_chat_id(id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"Pair not found: {id}")

    p = dict(p)
    v = security_verification.get(security_pair_id(p), {})
    p["status"] = v.get("status", "pending")
    p["note"] = v.get("note", "")

    try:
        from langchain_ollama import ChatOllama
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    except ImportError:
        raise HTTPException(status_code=500,
                            detail="langchain-ollama not installed. Run: pip install langchain-ollama")

    system_prompt = _build_security_system_prompt(p)

    lc_messages = [SystemMessage(content=system_prompt)]
    for m in body.messages:
        if m.role == "user":
            lc_messages.append(HumanMessage(content=m.content))
        elif m.role == "assistant":
            lc_messages.append(AIMessage(content=m.content))

    from utils.ollama_client import STAGE1_MODEL
    model_name = body.model or STAGE1_MODEL

    async def token_stream() -> AsyncIterator[str]:
        llm = ChatOllama(model=model_name, temperature=0.3)
        async for chunk in llm.astream(lc_messages):
            token = chunk.content
            if token:
                yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(token_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ══════════════════════════════════════════════════════════════════════════════
# BENCHMARK BROWSER  (/benchmark  and  /api/benchmark/*)
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/benchmark", response_class=HTMLResponse)
async def benchmark_index():
    return HTMLResponse(_BENCHMARK_HTML.read_text(encoding="utf-8"))


@app.get("/api/benchmark/records")
def get_benchmark_records(
    repo: Optional[str] = None,
    knowledge: Optional[str] = None,
    resolution: Optional[str] = None,
    q: Optional[str] = None,
    reviewer: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
):
    reviewer = valid_reviewer(reviewer)
    reviewed_ids = set(load_reviews(reviewer).keys()) if reviewer else set()
    filtered = []
    for i, r in enumerate(benchmark_records):
        if repo and r.get("repo") != repo:
            continue
        if knowledge:
            kinds = {p.get("knowledge_type") for p in (r.get("qa_pairs") or [])}
            if knowledge not in kinds:
                continue
        if resolution and (r.get("resolution_case") or "unset") != resolution:
            continue
        if q:
            ql = q.lower()
            searchable = " ".join([
                r.get("title", ""),
                r.get("security_topic", ""),
                r.get("qa_summary", ""),
                r.get("human_note", ""),
            ]).lower()
            if ql not in searchable:
                continue
        hf = r.get("hard_facts", {})
        qa_pairs = r.get("qa_pairs", []) or []
        filtered.append({
            "index": i,
            "id": r["id"],
            "repo": r.get("repo"),
            "number": r.get("number"),
            "title": r.get("title"),
            "state": r.get("state"),
            "security_topic": r.get("security_topic"),
            "qa_summary": r.get("qa_summary"),
            "answerer_role": r.get("answerer_role"),
            "llm_confidence": r.get("llm_confidence"),
            "has_cve": bool(hf.get("cve_ids")),
            "has_ghsa": bool(hf.get("ghsa_ids")),
            "has_fix": bool(hf.get("fix_prs") or hf.get("fix_commits")),
            "has_advisory": bool(hf.get("advisory_urls")),
            "resolution_case": r.get("resolution_case"),
            "n_fix_artifacts": len(r.get("fix_artifacts") or []),
            "has_base_commit": bool(r.get("base_commit")),
            "n_pairs": len(qa_pairs),
            "knowledge_types": sorted({p.get("knowledge_type") for p in qa_pairs if p.get("knowledge_type")}),
            "human_note": r.get("human_note", ""),
            "reviewed": r["id"] in reviewed_ids,
        })
    total = len(filtered)
    start = (page - 1) * page_size
    return {"total": total, "page": page, "page_size": page_size,
            "items": filtered[start: start + page_size]}


@app.get("/api/benchmark/records/{index}")
def get_benchmark_record(index: int, reviewer: Optional[str] = None):
    if index < 0 or index >= len(benchmark_records):
        raise HTTPException(status_code=404, detail="Record not found")
    reviewer = valid_reviewer(reviewer)
    base = benchmark_records[index]
    # In review mode, overlay this reviewer's own saved edits + rubrics (not the
    # author's shared overlay), so each reviewer sees/continues their own work.
    entry = load_reviews(reviewer).get(base["id"], {}) if reviewer else {}
    r = apply_overlay_fields(base, entry) if reviewer else base
    rub_overlay = entry.get("rubrics") or {}
    rubrics = {}
    for p in r.get("qa_pairs") or []:
        qid = p.get("qid")
        if qid:
            mr = merged_rubric(qid, rub_overlay.get(qid) if reviewer else None)
            if mr is not None:
                rubrics[qid] = mr
    return dict(r) | {"index": index, "rubrics": rubrics, "reviewer": reviewer,
                      "reviewed": bool(entry), "confirmed": bool(entry.get("confirmed")),
                      "edited": bool(entry.get("fields") or entry.get("rubrics"))}


@app.patch("/api/benchmark/records/{index}")
def update_benchmark_record(index: int, body: BenchmarkEditRequest,
                            reviewer: Optional[str] = None):
    if index < 0 or index >= len(benchmark_records):
        raise HTTPException(status_code=404, detail="Record not found")
    reviewer = valid_reviewer(reviewer)

    # Review mode: write edited fields to this reviewer's section of dataset/reviews.json
    # and DO NOT touch the shared benchmark file. Whole-record / arbitrary-field edits are
    # disabled here to keep per-dimension agreement well-defined.
    if reviewer:
        rid = benchmark_records[index]["id"]
        reviews = load_reviews(reviewer)
        entry = reviews.setdefault(rid, {})
        fields = entry.setdefault("fields", {})
        for k in _OVERLAY_FIELDS:
            v = getattr(body, k)
            if v is None:
                continue
            if k == "hard_facts":
                hf = dict(fields.get("hard_facts") or {})
                hf.update(v)
                fields["hard_facts"] = hf
            else:
                fields[k] = v
        entry["reviewer"] = reviewer
        entry["id"] = rid
        entry["reviewed_at"] = datetime.utcnow().isoformat() + "Z"
        save_reviews(reviewer, reviews)
        return {"ok": True, "reviewer": reviewer}

    r = benchmark_records[index]

    # Whole-record overwrite (raw-JSON editor): replace in place, keep the existing
    # `id` if the editor dropped it, and strip transient display-only keys.
    if body.full is not None:
        new = {k: v for k, v in body.full.items() if k not in _TRANSIENT_KEYS}
        new.setdefault("id", r.get("id"))
        benchmark_records[index] = new
        save_benchmark_data()
        return {"ok": True}

    if body.qa_summary is not None:
        r["qa_summary"] = body.qa_summary
    if body.security_topic is not None:
        r["security_topic"] = body.security_topic
    if body.human_note is not None:
        r["human_note"] = body.human_note
    if body.question_comment_id is not None:
        r["question_comment_id"] = body.question_comment_id
    if body.answer_comment_id is not None:
        r["answer_comment_id"] = body.answer_comment_id
    if body.answerer_role is not None:
        r["answerer_role"] = body.answerer_role
    if body.resolution_case is not None:
        r["resolution_case"] = body.resolution_case
    if body.artifacts_needed is not None:
        r["artifacts_needed"] = body.artifacts_needed
    if body.hard_facts is not None:
        existing = r.get("hard_facts", {})
        existing.update(body.hard_facts)
        r["hard_facts"] = existing
    if body.qa_pairs is not None:
        r["qa_pairs"] = body.qa_pairs
    # arbitrary top-level fields (title, authors, labels, state, …)
    for k, v in (body.fields or {}).items():
        if k not in _TRANSIENT_KEYS:
            r[k] = v
    save_benchmark_data()
    return {"ok": True}


@app.get("/api/benchmark/stats")
def get_benchmark_stats():
    kinds: dict[str, int] = {"parametric": 0, "grounded": 0}
    n_pairs = 0
    rec_with = {"parametric": 0, "grounded": 0}
    for r in benchmark_records:
        present = set()
        for p in r.get("qa_pairs") or []:
            k = p.get("knowledge_type")
            n_pairs += 1
            if k in kinds:
                kinds[k] += 1
                present.add(k)
        for k in present:
            rec_with[k] += 1
    return {
        "records": len(benchmark_records),
        "n_pairs": n_pairs,
        "kinds": kinds,                 # pair counts by type
        "records_with": rec_with,       # record counts containing ≥1 of type
        "repos": len({r.get("repo") for r in benchmark_records}),
    }


@app.get("/api/benchmark/repos")
def get_benchmark_repos():
    return sorted({r.get("repo", "") for r in benchmark_records})


@app.post("/api/benchmark/reload")
def reload_benchmark():
    load_benchmark_data()
    load_rubrics_data()
    return {"ok": True, "total": len(benchmark_records)}


def _record_id_for_qid(qid: str) -> Optional[str]:
    for r in benchmark_records:
        for p in r.get("qa_pairs") or []:
            if p.get("qid") == qid:
                return r["id"]
    return None


@app.post("/api/benchmark/records/{index}/review")
def set_review_status(index: int, reviewer: Optional[str] = None, confirmed: bool = True):
    """Mark a record reviewed without requiring a field edit — for the case where the
    reviewer checked everything and it all looks correct. `confirmed=false` un-marks it
    (removes the entry if the reviewer made no edits)."""
    reviewer = valid_reviewer(reviewer)
    if not reviewer:
        raise HTTPException(400, "reviewer query param required")
    if index < 0 or index >= len(benchmark_records):
        raise HTTPException(404, "Record not found")
    rid = benchmark_records[index]["id"]
    reviews = load_reviews(reviewer)
    entry = reviews.get(rid, {})
    if confirmed:
        entry["reviewer"] = reviewer
        entry["id"] = rid
        entry["confirmed"] = True
        entry["reviewed_at"] = datetime.utcnow().isoformat() + "Z"
        reviews[rid] = entry
    else:
        # un-confirm: drop the confirmed flag; remove the whole entry if no edits remain
        entry.pop("confirmed", None)
        if entry.get("fields") or entry.get("rubrics"):
            reviews[rid] = entry
        else:
            reviews.pop(rid, None)
    save_reviews(reviewer, reviews)
    return {"ok": True, "confirmed": confirmed and bool(reviews.get(rid))}


@app.post("/api/benchmark/rubric")
def save_rubric(body: RubricSaveRequest, reviewer: Optional[str] = None):
    """Persist the verification overlay for one qid's rubric. With ?reviewer set, the
    edit goes to that reviewer's section of dataset/reviews.json (keyed by record id),
    not the shared author overlay."""
    reviewer = valid_reviewer(reviewer)
    if reviewer:
        rid = _record_id_for_qid(body.qid)
        if rid is None:
            raise HTTPException(404, f"no benchmark record contains qid {body.qid}")
        draft = rubrics_by_qid.get(body.qid) or {}
        reviews = load_reviews(reviewer)
        entry = reviews.setdefault(rid, {})
        rub = dict((entry.get("rubrics") or {}).get(body.qid) or {})
        rub["rubric"] = body.rubric if body.rubric is not None else rub.get("rubric", draft.get("rubric", []))
        if body.acceptable_alternatives is not None:
            rub["acceptable_alternatives"] = body.acceptable_alternatives
        if body.note is not None:
            rub["note"] = body.note
        rub["status"] = body.status or rub.get("status", "edited")
        entry.setdefault("rubrics", {})[body.qid] = rub
        entry["reviewer"] = reviewer
        entry["id"] = rid
        entry["reviewed_at"] = datetime.utcnow().isoformat() + "Z"
        save_reviews(reviewer, reviews)
        return {"ok": True, "status": rub["status"], "reviewer": reviewer}

    cur = dict(rubrics_verified.get(body.qid) or {})
    draft = rubrics_by_qid.get(body.qid) or {}
    cur["rubric"] = body.rubric if body.rubric is not None else cur.get("rubric", draft.get("rubric", []))
    if body.acceptable_alternatives is not None:
        cur["acceptable_alternatives"] = body.acceptable_alternatives
    if body.note is not None:
        cur["note"] = body.note
    cur["status"] = body.status or cur.get("status", "edited")
    rubrics_verified[body.qid] = cur
    save_rubrics_verified()
    return {"ok": True, "status": cur["status"]}


@app.post("/api/benchmark/rubric-reload")
def reload_rubrics():
    load_rubrics_data()
    return {"ok": True, "n_drafts": len(rubrics_by_qid), "n_verified": len(rubrics_verified)}


# ══════════════════════════════════════════════════════════════════════════════
# OPEN-CODING REVIEW  (/open-coding  and  /api/oc/*)
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/open-coding", response_class=HTMLResponse)
async def oc_index():
    return HTMLResponse(_OC_HTML.read_text(encoding="utf-8"))


@app.get("/api/oc/records")
def get_oc_records(
    repo: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 200,
):
    filtered = []
    for i, r in enumerate(oc_records):
        v = oc_verified.get(r["id"], {})
        vstatus = v.get("status", "pending")

        if repo and r.get("repo") != repo:
            continue
        if status and vstatus != status:
            continue
        if q:
            ql = q.lower()
            searchable = " ".join([
                r.get("title", ""),
                r.get("qa_summary", ""),
                " ".join(v.get("codes", r.get("codes", []))),
            ]).lower()
            if ql not in searchable:
                continue

        codes = v.get("codes", r.get("codes", []))
        filtered.append({
            "index": i,
            "id": r["id"],
            "repo": r.get("repo"),
            "number": r.get("number"),
            "title": r.get("title"),
            "codes": codes,
            "model": r.get("model"),
            "status": vstatus,
            "note": v.get("note", ""),
        })

    total = len(filtered)
    start = (page - 1) * page_size
    return {"total": total, "page": page, "page_size": page_size,
            "items": filtered[start: start + page_size]}


@app.get("/api/oc/records/{index}")
def get_oc_record(index: int):
    if index < 0 or index >= len(oc_records):
        raise HTTPException(status_code=404, detail="Record not found")
    r = dict(oc_records[index])
    v = oc_verified.get(r["id"], {})
    r["index"] = index
    r["status"] = v.get("status", "pending")
    r["codes"] = v.get("codes", r.get("codes", []))
    r["rationale"] = v.get("rationale", r.get("rationale", ""))
    r["note"] = v.get("note", "")
    r["verified_at"] = v.get("verified_at", "")
    r["llm_codes"] = oc_records[index].get("codes", [])   # original LLM output
    return r


@app.post("/api/oc/records/{index}/save")
def save_oc_record(index: int, body: OCSaveRequest):
    if index < 0 or index >= len(oc_records):
        raise HTTPException(status_code=404, detail="Record not found")
    if body.status not in ("accepted", "rejected", "pending"):
        raise HTTPException(status_code=400, detail="Invalid status")
    rec_id = oc_records[index]["id"]
    oc_verified[rec_id] = {
        "status": body.status,
        "codes": [c.strip() for c in body.codes if c.strip()],
        "rationale": body.rationale or "",
        "note": body.note or "",
        "verified_at": datetime.utcnow().isoformat() + "Z",
    }
    save_oc_verified()
    return {"ok": True}


@app.get("/api/oc/stats")
def get_oc_stats():
    counts = {"accepted": 0, "rejected": 0, "pending": 0}
    repos: dict[str, int] = {}
    for r in oc_records:
        v = oc_verified.get(r["id"], {})
        s = v.get("status", "pending")
        counts[s] = counts.get(s, 0) + 1
        repo = r.get("repo", "unknown")
        repos[repo] = repos.get(repo, 0) + 1
    return {"total": len(oc_records), "counts": counts, "repos": repos}


@app.post("/api/oc/reload")
def reload_oc():
    load_oc_data()
    return {"ok": True, "total": len(oc_records)}


@app.post("/api/oc/export")
def export_oc():
    accepted = []
    for r in oc_records:
        v = oc_verified.get(r["id"], {})
        if v.get("status") == "accepted":
            out = dict(r)
            out["codes"] = v["codes"]
            out["rationale"] = v.get("rationale", "")
            out["note"] = v.get("note", "")
            out.pop("comments", None)   # strip raw thread to keep file lean
            accepted.append(out)
    with OC_EXPORT_FILE.open("w", encoding="utf-8") as f:
        for rec in accepted:
            f.write(json.dumps(rec) + "\n")
    return {"exported": len(accepted), "file": str(OC_EXPORT_FILE)}


@app.get("/api/oc/export/download")
def download_oc_export():
    if not OC_EXPORT_FILE.exists():
        raise HTTPException(status_code=404, detail="No export yet. Run export first.")
    return FileResponse(OC_EXPORT_FILE, filename="open_codes_verified.jsonl",
                        media_type="application/octet-stream")


@app.get("/api/oc/repos")
def get_oc_repos():
    return sorted({r.get("repo", "") for r in oc_records})


# ══════════════════════════════════════════════════════════════════════════════
# NORMALIZED EVAL-PAIRS REVIEW  (/normalized  and  /api/normalized/*)
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/normalized", response_class=HTMLResponse)
async def normalized_index():
    return HTMLResponse(_NORM_HTML.read_text(encoding="utf-8"))


@app.get("/api/normalized/records")
def get_norm_records(
    repo: Optional[str] = None,
    status: Optional[str] = None,
    knowledge: Optional[str] = None,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 500,
):
    filtered = []
    for i, r in enumerate(norm_records):
        pairs_ = r.get("qa_pairs", [])
        vstatus = _norm_status(r)
        kinds = [p.get("knowledge_type") for p in pairs_]

        if repo and r.get("repo") != repo:
            continue
        if status and vstatus != status:
            continue
        if knowledge and knowledge not in kinds:
            continue
        if q:
            ql = q.lower()
            searchable = " ".join(
                [r.get("title", "")]
                + [p.get("question", "") + " " + p.get("answer", "") for p in pairs_]
            ).lower()
            if ql not in searchable:
                continue

        filtered.append({
            "index": i,
            "id": r.get("thread_id"),
            "repo": r.get("repo"),
            "title": r.get("title"),
            "n_pairs": len(pairs_),
            "kinds": kinds,
            "status": vstatus,
            "has_leak": bool(r.get("leak_flags")),
            "has_error": bool(r.get("error")),
            "note": r.get("review_note", ""),
        })
    total = len(filtered)
    start = (page - 1) * page_size
    return {"total": total, "page": page, "page_size": page_size,
            "items": filtered[start: start + page_size]}


@app.get("/api/normalized/records/{index}")
def get_norm_record(index: int):
    if index < 0 or index >= len(norm_records):
        raise HTTPException(status_code=404, detail="Record not found")
    r = dict(norm_records[index])
    r["index"] = index
    r["id"] = r.get("thread_id")          # frontend keys list/detail on `id`
    r["status"] = _norm_status(r)
    r["review_note"] = r.get("review_note", "")
    r["reviewed_at"] = r.get("reviewed_at", "")
    # Join source thread for side-by-side review.
    src = norm_source_by_id.get(r.get("thread_id"), {})
    r["comments"] = src.get("comments", [])
    src_meta = r.get("source", {}) or {}
    r["question_comment_id"] = src_meta.get("question_comment_id") or src.get("question_comment_id")
    r["answer_comment_id"] = src_meta.get("answer_comment_id") or src.get("answer_comment_id")
    r["reporter"] = src.get("reporter")
    r["answer_author"] = src.get("answer_author")
    return r


@app.patch("/api/normalized/records/{index}")
def update_norm_record(index: int, body: NormSaveRequest):
    if index < 0 or index >= len(norm_records):
        raise HTTPException(status_code=404, detail="Record not found")
    if body.status not in ("approved", "rejected", "pending"):
        raise HTTPException(status_code=400, detail="Invalid status")
    r = norm_records[index]
    hard_facts = r.get("hard_facts", {})

    new_pairs = []
    all_leaks = []
    for j, p in enumerate(body.qa_pairs):
        ktype = p.knowledge_type if p.knowledge_type in ("parametric", "grounded") else "grounded"
        sources = [] if ktype == "parametric" else [s for s in p.grounding_sources if s.strip()]
        leaks = _fix_leak_flags(p.question, hard_facts)
        all_leaks += leaks
        new_pairs.append({
            "qid": p.qid or f"{r.get('thread_id')}#{j+1}",
            "question": p.question.strip(),
            "answer": p.answer.strip(),
            "knowledge_type": ktype,
            "grounding_sources": sources,
            "answer_grounded_in": p.answer_grounded_in,
            "leak_flags": leaks,
        })

    r["qa_pairs"] = new_pairs
    r["leak_flags"] = all_leaks
    r["review_status"] = body.status
    r["approved"] = (body.status == "approved")
    r["needs_review"] = (body.status == "pending")
    r["review_note"] = body.note or ""
    r["reviewed_at"] = datetime.utcnow().isoformat() + "Z"
    save_norm_data()
    return {"ok": True}


@app.get("/api/normalized/stats")
def get_norm_stats():
    counts = {"approved": 0, "rejected": 0, "pending": 0}
    kinds = {"parametric": 0, "grounded": 0}
    n_pairs = 0
    for r in norm_records:
        counts[_norm_status(r)] = counts.get(_norm_status(r), 0) + 1
        for p in r.get("qa_pairs", []):
            n_pairs += 1
            k = p.get("knowledge_type")
            if k in kinds:
                kinds[k] += 1
    return {"total": len(norm_records), "n_pairs": n_pairs,
            "counts": counts, "kinds": kinds}


@app.get("/api/normalized/repos")
def get_norm_repos():
    return sorted({r.get("repo", "") for r in norm_records if r.get("repo")})


@app.post("/api/normalized/reload")
def reload_norm():
    load_norm_data()
    return {"ok": True, "total": len(norm_records)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8765,
        reload=True,
        app_dir=str(Path(__file__).parent),
    )
