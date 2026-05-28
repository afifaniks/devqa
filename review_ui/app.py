#!/usr/bin/env python3
"""FastAPI review UI — three separate pipelines.

/          → F&M classified pairs   (natural_qa_pairs_dual_stage.jsonl)
/open      → Open-coded pairs       (open_qa_pairs.jsonl)
/security  → Security QA pairs      (security_qa_pairs.jsonl)
"""

import json
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
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
        verification = json.loads(VERIFICATION_FILE.read_text())
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
        open_verification = json.loads(OPEN_VERIFICATION_FILE.read_text())
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
        security_verification = json.loads(SECURITY_VERIFICATION_FILE.read_text())
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


# ── App ───────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_data()
    load_open_data()
    load_security_data()
    print(
        f"Loaded {len(pairs)} F&M pairs, {len(open_pairs)} open-coded pairs, "
        f"{len(security_pairs)} security pairs",
        file=sys.stderr,
    )
    yield


_INDEX_HTML = Path(__file__).parent / "templates" / "index.html"
_TAXONOMY_HTML = Path(__file__).parent / "templates" / "taxonomy.html"
_STATS_HTML = Path(__file__).parent / "templates" / "stats.html"

app = FastAPI(title="DevQA – Pair Review Tool", lifespan=lifespan)
app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)


# ── Shared pages ──────────────────────────────────────────────────────────────


@app.get("/taxonomy", response_class=HTMLResponse)
async def taxonomy_page():
    return HTMLResponse(_TAXONOMY_HTML.read_text())


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
    return HTMLResponse(_INDEX_HTML.read_text())


@app.get("/stats", response_class=HTMLResponse)
async def stats_page():
    return HTMLResponse(_STATS_HTML.read_text())


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
    return HTMLResponse(_INDEX_HTML.read_text())


@app.get("/open/stats", response_class=HTMLResponse)
async def open_stats_page():
    return HTMLResponse(_STATS_HTML.read_text())


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
    return HTMLResponse(_INDEX_HTML.read_text())


@app.get("/security/stats", response_class=HTMLResponse)
async def security_stats_page():
    return HTMLResponse(_STATS_HTML.read_text())


@app.get("/api/security/pairs")
def get_security_pairs(
    repo: Optional[str] = None,
    status: Optional[str] = None,
    verifiability: Optional[str] = None,
    answerer_role: Optional[str] = None,
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
        if verifiability and p.get("verifiability") != verifiability:
            continue
        if answerer_role and p.get("answerer_role") != answerer_role:
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
            "repo": p.get("repo"),
            "question_id": "SECURITY_OPEN",
            "number": p.get("number"),
            "need_summary": p.get("need_summary", ""),
            "security_topic": p.get("security_topic", ""),
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


@app.get("/api/security/pairs/{index}")
def get_security_pair(index: int):
    if index < 0 or index >= len(security_pairs):
        raise HTTPException(status_code=404, detail="Pair not found")
    p = dict(security_pairs[index])
    v = security_verification.get(security_pair_id(p), {})
    p["index"] = index
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
    role_counts: dict[str, int] = {}
    verif_counts: dict[str, int] = {}
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
        role = p.get("answerer_role", "?")
        role_counts[role] = role_counts.get(role, 0) + 1
        verif = p.get("verifiability", "?")
        verif_counts[verif] = verif_counts.get(verif, 0) + 1

    return {
        "total": len(security_pairs),
        "counts": counts,
        "repos": repos,
        "question_ids": {"SECURITY_OPEN": len(security_pairs)},
        "categories": topic_counts,
        "cat_status": topic_status,
        "answerer_roles": role_counts,
        "verifiability": verif_counts,
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8765,
        reload=True,
        app_dir=str(Path(__file__).parent),
    )
