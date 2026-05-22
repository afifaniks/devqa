#!/usr/bin/env python3
"""FastAPI review UI for validating natural_qa_pairs.jsonl data."""

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
VERIFICATION_FILE = ROOT / "verified_state.json"
EXPORT_FILE = ROOT / "verified_qa_pairs.jsonl"

sys.path.insert(0, str(ROOT / "pipeline"))
from utils.taxonomy import CATEGORIES, QUESTIONS, QUESTION_TO_CATEGORY  # noqa: E402

# ── In-memory data ──────────────────────────────────────────────────────────

pairs: list[dict] = []
verification: dict[str, dict] = {}  # key = pair_id (repo/source/number/question_id)


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
    for jsonl_file in sorted(OUTPUT_DIR.glob("*/natural_qa_pairs.jsonl")):
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


# ── Models ──────────────────────────────────────────────────────────────────


class VerifyRequest(BaseModel):
    status: str  # "accepted" | "rejected" | "pending"
    note: Optional[str] = ""


class AssignRequest(BaseModel):
    question_id: str


# ── App ──────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_data()
    print(f"Loaded {len(pairs)} pairs from {OUTPUT_DIR}", file=sys.stderr)
    yield


_INDEX_HTML = Path(__file__).parent / "templates" / "index.html"
_TAXONOMY_HTML = Path(__file__).parent / "templates" / "taxonomy.html"
_STATS_HTML = Path(__file__).parent / "templates" / "stats.html"

app = FastAPI(title="DevQA – Pair Review Tool", lifespan=lifespan)
app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)


# ── Routes ──────────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(_INDEX_HTML.read_text())


@app.get("/taxonomy", response_class=HTMLResponse)
async def taxonomy_page():
    return HTMLResponse(_TAXONOMY_HTML.read_text())


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

        filtered.append(
            {
                "index": i,
                "repo": p.get("repo"),
                "question_id": v.get("question_id_override", p.get("question_id")),
                "number": p.get("number"),
                "question_text": p.get("question_text", ""),
                "title": p.get("title"),
                "confidence": p.get("confidence"),
                "stage1_category": p.get("stage1_category") or p.get("category"),
                "source": p.get("source"),
                "status": vstatus,
                "note": v.get("note", ""),
            }
        )

    total = len(filtered)
    start = (page - 1) * page_size
    page_items = filtered[start : start + page_size]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": page_items,
    }


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
        repo = p.get("repo", "unknown")
        repos[repo] = repos.get(repo, 0) + 1

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
    accepted = [
        p for p in pairs if verification.get(pair_id(p), {}).get("status") == "accepted"
    ]
    with EXPORT_FILE.open("w") as f:
        for p in accepted:
            f.write(json.dumps(p) + "\n")
    return {"exported": len(accepted), "file": str(EXPORT_FILE)}


@app.get("/api/export/download")
def download_export():
    if not EXPORT_FILE.exists():
        raise HTTPException(status_code=404, detail="No export yet. Run export first.")
    return FileResponse(
        EXPORT_FILE,
        filename="verified_qa_pairs.jsonl",
        media_type="application/octet-stream",
    )


@app.get("/api/taxonomy")
def get_taxonomy():
    return {
        "categories": {k: {"name": v[0], "qs": v[1]} for k, v in CATEGORIES.items()},
        "questions": QUESTIONS,
    }


@app.get("/api/repos")
def get_repos():
    repos = sorted({p.get("repo", "") for p in pairs})
    return repos


@app.get("/api/question_ids")
def get_question_ids():
    qids = sorted({p.get("question_id", "") for p in pairs})
    return qids


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8765,
        reload=True,
        app_dir=str(Path(__file__).parent),
    )
