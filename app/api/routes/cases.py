"""Case evaluation endpoints — inspect RAG knowledge per generation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.case_capture import list_cases, load_case, load_case_knowledge

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("")
async def list_evaluation_cases(limit: int = 50) -> dict:
    """List saved generation cases (newest first) for RAG evaluation."""
    cases = list_cases(limit=max(1, min(limit, 200)))
    return {"success": True, "count": len(cases), "cases": cases}


@router.get("/{case_id}")
async def get_evaluation_case(case_id: str) -> dict:
    """Full case bundle: input + knowledge + package output."""
    case = load_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
    return {"success": True, **case}


@router.get("/{case_id}/knowledge")
async def get_case_knowledge(case_id: str) -> dict:
    """Full Retriever knowledge JSON for one case."""
    knowledge = load_case_knowledge(case_id)
    if knowledge is None:
        raise HTTPException(status_code=404, detail=f"Knowledge not found for case: {case_id}")
    return {"success": True, "caseId": case_id, "knowledge": knowledge}
