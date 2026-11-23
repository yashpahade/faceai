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
from faceai.api.routes import router
from faceai.config import Settings, get_settings
from faceai.logging import request_id_ctx, setup_logging
from faceai.models.card import load_card
from faceai.service import RecognitionService
from faceai.store.db import Database
from faceai.vision.types import FaceEngineProtocol

logger = logging.getLogger("faceai.api")


def _build_engine(settings: Settings) -> FaceEngineProtocol:
    from faceai.vision.engine import FaceEngine  # heavy import (onnxruntime) sirf yahan

    engine = FaceEngine(
        settings.models_dir, settings.model_pack, settings.det_size, settings.device
    )
    engine.warmup()
    return engine


def create_app(
    settings: Settings | None = None, engine: FaceEngineProtocol | None = None
) -> FastAPI:
    """`engine` inject kar sakte ho (tests mein fake engine).

    Isse Dependency Injection kehte hain.
    """
    settings = settings or get_settings()
    setup_logging(settings.log_level, settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("starting faceai v%s (env=%s)", __version__, settings.env)
        app.state.settings = settings
        app.state.service = None
        app.state.model_card = None
        app.state.ready = False
        db = Database(settings.db_path)
        try:
            t0 = time.perf_counter()
            eng = engine or _build_engine(settings)
            # Registry version info (Phase 3). Fake engine (tests) ke saath card nahi padhte.
            app.state.model_card = (
                None if engine else load_card(settings.models_dir / settings.model_pack)
            )
            app.state.service = RecognitionService(eng, db, settings)
            app.state.ready = True
            logger.info(
                "model ready: %s on %s (%.1fs)", eng.model_id, eng.device, time.perf_counter() - t0
            )
        except Exception:
            # App zinda rahe (liveness OK) par ready nahi -> load balancer traffic nahi bhejega
            logger.exception("model load failed; service NOT ready")
        yield
        db.close()
        logger.info("shutting down")

    app = FastAPI(title="FaceAI", version=__version__, lifespan=lifespan)
    app.include_router(router)

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
    def version(request: Request) -> dict:
        svc = getattr(request.app.state, "service", None)
        card = getattr(request.app.state, "model_card", None) or {}
        return {
            "app_version": __version__,
            "env": settings.env,
            "model_id": svc.engine.model_id if svc else None,
            "device": svc.engine.device if svc else None,
            # MLflow registry version (models/<pack>/model_card.json se; null = unregistered)
            "model_version": card.get("version"),
            "model_alias": card.get("alias"),
            "match_threshold": settings.match_threshold,
            "recommended_threshold": (card.get("recommended_threshold") or {}).get("threshold"),
        }

    return app
