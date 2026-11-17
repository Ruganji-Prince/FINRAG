import json
import logging
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from threading import Lock

from fastapi import FastAPI, HTTPException, Request

from backend.config import ROOT, settings
from backend.database import documents, initialize, rows, stats
from backend.rag import answer, search
from backend.schemas import (
    AnswerResponse,
    Compare,
    ComparisonResponse,
    Filters,
    Query,
    SearchResponse,
)

log = logging.getLogger("finrag")


@asynccontextmanager
async def lifespan(app):
    if settings.public_mode and len(settings.api_access_token) < 32:
        raise RuntimeError(
            "Public mode requires an API access token of at least 32 characters"
        )
    if settings.auto_migrate:
        initialize()
    else:
        rows("SELECT 1 AS ready")
    if settings.preload_models:
        if settings.embedding_backend == "sentence-transformers":
            from backend.embeddings import model

            model()
        if settings.llm_provider == "local":
            from backend.providers import local_model

            local_model()
    yield


app = FastAPI(
    title="FinRAG - Rwanda Financial Intelligence", version="0.1.0", lifespan=lifespan
)
windows = defaultdict(deque)
lock = Lock()


@app.middleware("http")
async def limits(request: Request, call_next):
    from starlette.responses import JSONResponse

    if settings.public_mode and len(settings.api_access_token) < 32:
        return JSONResponse(
            {"detail": "Public service is not configured"}, status_code=503
        )
    if settings.api_access_token and request.url.path != "/health":
        supplied = request.headers.get("authorization", "")
        if not secrets.compare_digest(
            supplied.encode(), ("Bearer " + settings.api_access_token).encode()
        ):
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
    # Count actual streamed bytes as well as Content-Length; chunked uploads cannot bypass this bound.
    if request.method in {"POST", "PUT", "PATCH"}:
        size = 0
        chunks = []
        async for chunk in request.stream():
            size += len(chunk)
            if size > settings.max_request_bytes:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
            chunks.append(chunk)
        request._body = b"".join(chunks)
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with lock:
        for old_key in list(windows):
            if not windows[old_key] or now - windows[old_key][-1] > 60:
                del windows[old_key]
        window = windows[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= settings.requests_per_minute:
            return JSONResponse(
                {"detail": "Rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        window.append(now)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    log.info(
        json.dumps(
            {
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - now) * 1000, 2),
            }
        )
    )
    return response


@app.exception_handler(Exception)
async def unexpected(request, exc):
    from starlette.responses import JSONResponse

    log.error("request_failed type=%s", type(exc).__name__)
    return JSONResponse(
        {"detail": "Service unavailable. Check local server logs."}, status_code=503
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mode": settings.llm_provider,
        "embedding_backend": settings.embedding_backend,
        "embedding_model": __import__(
            "backend.embeddings", fromlist=["identity"]
        ).identity(),
        "database": "postgresql"
        if settings.database_url.startswith("postgresql")
        else "sqlite",
        "database_ready": bool(rows("SELECT 1 AS ready")),
    }


@app.get("/documents")
def library():
    return [{k: v for k, v in d.items() if k != "path"} for d in documents()]


@app.post("/search", response_model=SearchResponse)
def passages(query: Query):
    return {"evidence": search(query)}


@app.post("/ask", response_model=AnswerResponse)
def ask(query: Query):
    return answer(query)


@app.post("/compare", response_model=ComparisonResponse)
def compare(query: Compare):
    ids = {d["id"] for d in documents()}
    if not {query.left_id, query.right_id} <= ids:
        raise HTTPException(404, "Document not found")
    left = answer(
        Query(question=query.topic, k=3, filters=Filters(document_id=query.left_id)),
        generate_answer=False,
    )
    right = answer(
        Query(question=query.topic, k=3, filters=Filters(document_id=query.right_id)),
        generate_answer=False,
    )
    comparison = None
    if settings.llm_provider != "none" and left["evidence"] and right["evidence"]:
        evidence = left["evidence"][:2] + right["evidence"][:2]
        comparison = answer(
            Query(
                question="Compare the reported "
                + query.topic
                + " in the two selected reports. Cite evidence from BOTH reports."
            ),
            evidence_override=evidence,
        )
        cited = {claim["chunk_id"] for claim in comparison["claims"]}
        covered = {e["document_id"] for e in evidence if e["chunk_id"] in cited}
        if not comparison["abstained"] and covered != {query.left_id, query.right_id}:
            comparison.update(
                abstained=True,
                answer="The generated comparison did not support both reports. Review the individual source passages.",
                claims=[],
            )
    return {
        "topic": query.topic,
        "left": left,
        "right": right,
        "comparison": comparison,
        "interpretation": "Side-by-side report evidence. Differences may reflect reporting periods, definitions or revisions; verify comparability.",
    }


@app.get("/quality")
def quality():
    return stats()


@app.get("/governance")
def governance():
    return {
        "registry": json.loads(
            rows(
                "SELECT payload_json FROM governance_records WHERE registry_key=?",
                ("project_registry",),
            )[0]["payload_json"]
        ),
        "catalogue": library(),
        "records": rows("SELECT * FROM governance_records ORDER BY registry_key"),
        "transfers": rows("SELECT * FROM data_transfers ORDER BY completed_at DESC"),
        "embedding_runs": rows("SELECT * FROM embedding_runs ORDER BY started_at DESC"),
        "lineage": stats()["lineage"],
    }


@app.get("/evaluation")
def evaluation():
    folder = ROOT / "evaluation/results"
    path = folder / "rag-latest.json"
    if not path.exists():
        path = folder / "latest.json"
    result = (
        json.loads(path.read_text())
        if path.exists()
        else {"status": "not_run", "metrics": None}
    )
    comparison = folder / "retrieval-comparison.json"
    if comparison.exists():
        result["retrieval_comparison"] = json.loads(comparison.read_text())["metrics"]
    return result
