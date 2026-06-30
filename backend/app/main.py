"""FastAPI application factory and entrypoint.

Wires together configuration, logging, middleware, CORS, exception handlers,
the versioned API router, and the root-level health/version/root endpoints.

Sprint 0 scope: foundation only. No business, AI, or ranking logic.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.db import dispose_engine
from app.middleware import RequestLoggingMiddleware
from app.schemas import HealthResponse, RootResponse, VersionResponse

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Manage startup/shutdown side effects."""
    settings = get_settings()
    logger.info("Starting %s (env=%s)", settings.app_name, settings.app_env.value)
    yield
    logger.info("Shutting down — disposing database engine")
    await dispose_engine()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Custom middleware ───────────────────────────────────
    app.add_middleware(RequestLoggingMiddleware)

    # ── Exception handlers ──────────────────────────────────
    register_exception_handlers(app)

    # ── Versioned API ───────────────────────────────────────
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # ── Root-level endpoints ────────────────────────────────
    @app.get("/", response_model=RootResponse, tags=["root"], summary="Service root")
    async def root() -> RootResponse:
        return RootResponse(
            message=f"{settings.app_name} API",
            docs_url="/docs",
            health_url="/health",
        )

    @app.get("/health", response_model=HealthResponse, tags=["health"], summary="Health probe")
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", environment=settings.app_env.value)

    @app.get("/version", response_model=VersionResponse, tags=["meta"], summary="Service version")
    async def version() -> VersionResponse:
        return VersionResponse(
            name=settings.app_name,
            version=settings.app_version,
            api_version="v1",
        )

    return app


app = create_app()
