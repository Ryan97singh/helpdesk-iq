import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.api import admin, auth, chat, documents, tickets
from app.core.cache import get_cache
from app.core.config import get_settings
from app.core.logging import log_event, request_id_var, setup_logging
from app.core.metrics import HTTP_LATENCY, HTTP_REQUESTS
from app.db import engine, init_db

logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    init_db()  # demo convenience; production runs Alembic migrations as a pre-deploy job
    yield


settings = get_settings()
app = FastAPI(
    title="HelpdeskIQ API",
    version="1.0.0",
    description="AI IT/HR helpdesk copilot: RAG chat, AI ticket triage, multi-provider LLM gateway.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def observability(request: Request, call_next):
    """Request-ID propagation, access log, RED metrics and baseline security headers."""
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    token = request_id_var.set(rid)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled error")
        response = JSONResponse({"detail": "Internal server error", "request_id": rid}, status_code=500)
    elapsed = time.perf_counter() - started
    route = request.scope.get("route")
    path = route.path if route else "unmatched"  # templated path keeps metric cardinality bounded
    HTTP_REQUESTS.labels(request.method, path, response.status_code).inc()
    HTTP_LATENCY.labels(request.method, path).observe(elapsed)
    if path not in ("/metrics", "/health"):
        log_event(logger, "request", method=request.method, path=path,
                  status=response.status_code, duration_ms=int(elapsed * 1000))
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    request_id_var.reset(token)
    return response


for r in (auth.router, documents.router, chat.router, tickets.router, admin.router):
    app.include_router(r)


@app.get("/health", tags=["ops"])
def health():
    """Liveness: the process is up. Kept dependency-free so a DB blip doesn't restart every pod."""
    return {"status": "ok"}


@app.get("/ready", tags=["ops"])
def ready():
    """Readiness: dependencies reachable; the load balancer stops routing here if not."""
    checks = {}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "down"
    checks["cache"] = "ok" if get_cache().ping() else "down"
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse({"status": "ready" if ok else "degraded", "checks": checks}, status_code=200 if ok else 503)


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
