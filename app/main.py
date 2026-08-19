"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.dependencies import shutdown_resources
from app.api.exception_handlers import register_exception_handlers
from app.api.routes import cases, context, health, knowledge, packages, sme
from app.config.settings import get_app_settings
from app.utils.logging import setup_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    yield
    await shutdown_resources()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_app_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="ReTour AI Brain — tourism planning, RAG, SME intelligence, and package generation",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # credentials+wildcard breaks browser CORS; pin local wizard origins.
    origins = settings.cors_origins
    if origins == ["*"]:
        origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    api_prefix = settings.api_prefix
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(packages.router, prefix=api_prefix)
    app.include_router(knowledge.router, prefix=api_prefix)
    app.include_router(sme.router, prefix=api_prefix)
    app.include_router(context.router, prefix=api_prefix)
    app.include_router(cases.router, prefix=api_prefix)

    @app.get("/", include_in_schema=False)
    async def root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    return app


app = create_app()
