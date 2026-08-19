"""Context build API."""

from __future__ import annotations

from fastapi import APIRouter

from app.context.builder import build_planning_context
from app.planning.profile import normalize_tourist_profile
from app.schemas.request.package_request import PackageRequest

router = APIRouter(prefix="/context", tags=["context"])


@router.post("/build")
async def build_context(request: PackageRequest) -> dict:
    profile = normalize_tourist_profile(request)
    context = await build_planning_context(profile)
    return {"success": True, "profile": profile.prompt_dict(), "context": context.prompt_dict()}
