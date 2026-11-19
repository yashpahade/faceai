"""
FastAPI application factory.

Concepts:
- App factory (`create_app`): tests apni settings ke saath fresh app bana sakte hain.
- Lifespan: heavy cheezein (ML model) startup pe EK baar load hongi (Phase 1).
- Liveness vs Readiness (Kubernetes concept):
    /health/live  -> process zinda hai? (fail => container restart)
    /health/ready -> traffic lene ko ready hai? (model load hua? fail => traffic mat bhejo)
- Request ID middleware: har request ko unique ID, response header + logs dono mein.
"""

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from faceai import __version__
from faceai.config import Settings, get_settings
from faceai.logging import request_id_ctx, setup_logging

logger = logging.getLogger("faceai.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level, settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("starting faceai v%s (env=%s)", __version__, settings.env)
        app.state.settings = settings
        # Phase 1: yahan face model + vector index load hoga, phir ready=True
        app.state.ready = True
        yield
        logger.info("shutting down")

    app = FastAPI(title="FaceAI", version=__version__, lifespan=lifespan)

    @app.middleware("http")
    async def request_context(request: Request, call_next) -> Response:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        token = request_id_ctx.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled error on %s %s", request.method, request.url.path)
            response = JSONResponse({"detail": "internal server error"}, status_code=500)
        latency_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = rid
        logger.info(
            "%s %s -> %d (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            latency_ms,
            extra={"latency_ms": round(latency_ms, 2), "status": response.status_code},
        )
        request_id_ctx.reset(token)
        return response

    @app.get("/health/live", tags=["health"])
    def live() -> dict:
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"])
    def ready(request: Request) -> JSONResponse:
        is_ready = getattr(request.app.state, "ready", False)
        return JSONResponse(
            {"status": "ready" if is_ready else "not_ready"},
            status_code=200 if is_ready else 503,
        )

    @app.get("/version", tags=["meta"])
    def version() -> dict:
        # Phase 3: yahan model name + model version (MLflow registry se) bhi aayega
        return {"app_version": __version__, "env": settings.env}

    return app
