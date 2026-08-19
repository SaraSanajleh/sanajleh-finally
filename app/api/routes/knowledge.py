"""Knowledge search API — useful for debugging and future clients."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_knowledge_provider
from app.context.builder import build_planning_context
from app.planning.profile import normalize_tourist_profile
from app.planning.route import apply_open_trip_evidence
from app.retrieval.composer import compose_trip_knowledge
from app.schemas.request.package_request import PackageRequest
from app.services.retriever_client import TourismKnowledgeProvider

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/search")
async def search_knowledge(
    request: PackageRequest,
    knowledge: TourismKnowledgeProvider = Depends(get_knowledge_provider),
) -> dict:
    raw = await knowledge.search_for_itinerary(request)
    profile = normalize_tourist_profile(request)
    profile, inferred = apply_open_trip_evidence(profile, raw)
    context = await build_planning_context(profile, inferred_dests=inferred)
    composed = compose_trip_knowledge(raw, profile, context)
    return {
        "success": True,
        "status": composed.status,
        "knowledge": composed.prompt_dict(),
        "raw_meta": raw.get("meta") or {},
    }
