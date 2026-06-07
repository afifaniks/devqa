#!/usr/bin/env python3
"""FastAPI review UI — three separate pipelines + benchmark browser.

/          → F&M classified pairs   (natural_qa_pairs_dual_stage.jsonl)
/open      → Open-coded pairs       (open_qa_pairs.jsonl)
/security  → Security QA pairs      (security_qa_pairs.jsonl)
/benchmark → Security benchmark     (dataset/security_benchmark.jsonl)
"""

import json
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Optional

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

# ── Open-coding review files ───────────────────────────────────────────────────
OC_CODES_FILE = ROOT / "dataset" / "open_codes.jsonl"
OC_VERIFIED_FILE = ROOT / "dataset" / "open_codes_verified.json"
OC_EXPORT_FILE = ROOT / "dataset" / "open_codes_verified.jsonl"

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
    artifacts_needed: Optional[list[str]] = None
    hard_facts: Optional[dict] = None


class OCSaveRequest(BaseModel):
    status: str           # "accepted" | "rejected" | "pending"
    codes: list[str]      # edited codes list
    rationale: Optional[str] = ""
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
    if BENCHMARK_FILE.exists():
        with BENCHMARK_FILE.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    benchmark_records.append(json.loads(line))


def save_benchmark_data() -> None:
    BENCHMARK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with BENCHMARK_FILE.open("w", encoding="utf-8") as f:
        for record in benchmark_records:
            f.write(json.dumps(record) + "\n")


# ── App ───────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_data()
    load_open_data()
    load_security_data()
    load_benchmark_data()
    load_oc_data()
    print(
        f"Loaded {len(pairs)} F&M pairs, {len(open_pairs)} open-coded pairs, "
        f"{len(security_pairs)} security pairs, {len(benchmark_records)} benchmark records, "
        f"{len(oc_records)} open-coding records",
        file=sys.stderr,
    )
    yield


_INDEX_HTML = Path(__file__).parent / "templates" / "index.html"
_TAXONOMY_HTML = Path(__file__).parent / "templates" / "taxonomy.html"
_STATS_HTML = Path(__file__).parent / "templates" / "stats.html"
_CHAT_HTML = Path(__file__).parent / "templates" / "chat.html"
_BENCHMARK_HTML = Path(__file__).parent / "templates" / "benchmark.html"
_OC_HTML = Path(__file__).parent / "templates" / "open_coding.html"

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
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
):
    filtered = []
    for i, r in enumerate(benchmark_records):
        if repo and r.get("repo") != repo:
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
        filtered.append({
            "index": i,
            "id": r["id"],
            "repo": r.get("repo"),
            "number": r.get("number"),
            "title": r.get("title"),
            "security_topic": r.get("security_topic"),
            "qa_summary": r.get("qa_summary"),
            "answerer_role": r.get("answerer_role"),
            "llm_confidence": r.get("llm_confidence"),
            "has_cve": bool(hf.get("cve_ids")),
            "has_fix": bool(hf.get("fix_prs") or hf.get("fix_commits")),
            "human_note": r.get("human_note", ""),
        })
    total = len(filtered)
    start = (page - 1) * page_size
    return {"total": total, "page": page, "page_size": page_size,
            "items": filtered[start: start + page_size]}


@app.get("/api/benchmark/records/{index}")
def get_benchmark_record(index: int):
    if index < 0 or index >= len(benchmark_records):
        raise HTTPException(status_code=404, detail="Record not found")
    return dict(benchmark_records[index]) | {"index": index}


@app.patch("/api/benchmark/records/{index}")
def update_benchmark_record(index: int, body: BenchmarkEditRequest):
    if index < 0 or index >= len(benchmark_records):
        raise HTTPException(status_code=404, detail="Record not found")
    r = benchmark_records[index]
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
    if body.artifacts_needed is not None:
        r["artifacts_needed"] = body.artifacts_needed
    if body.hard_facts is not None:
        existing = r.get("hard_facts", {})
        existing.update(body.hard_facts)
        r["hard_facts"] = existing
    save_benchmark_data()
    return {"ok": True}


@app.get("/api/benchmark/repos")
def get_benchmark_repos():
    return sorted({r.get("repo", "") for r in benchmark_records})


@app.post("/api/benchmark/reload")
def reload_benchmark():
    load_benchmark_data()
    return {"ok": True, "total": len(benchmark_records)}


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8765,
        reload=True,
        app_dir=str(Path(__file__).parent),
    )
