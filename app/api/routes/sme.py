"""SME search API."""

from __future__ import annotations

from fastapi import APIRouter

from app.planning.profile import normalize_tourist_profile
from app.schemas.request.package_request import PackageRequest
from app.sme.matcher import match_smes, select_package_smes

router = APIRouter(prefix="/sme", tags=["sme"])


@router.post("/search")
async def search_smes(request: PackageRequest) -> dict:
    profile = normalize_tourist_profile(request)
    team = select_package_smes(profile)
    matches = match_smes(profile)
    return {
        "success": True,
        "count": len(matches),
        "package_team": [match.prompt_card() for match in team],
        "candidates": [match.prompt_card() for match in matches],
    }
