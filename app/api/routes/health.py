"""Health check endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_llm_manager
from app.config.settings import get_app_settings
from app.llm.manager import LLMManager

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Basic liveness probe."""
    settings = get_app_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/health/llm")
async def llm_health_check(llm: LLMManager = Depends(get_llm_manager)) -> dict:
    """Check LLM provider connectivity."""
    is_healthy = await llm.health_check()
    return {
        "status": "ok" if is_healthy else "degraded",
        "provider": llm.provider_name,
        "model": llm.model_name,
        "reachable": is_healthy,
    }
