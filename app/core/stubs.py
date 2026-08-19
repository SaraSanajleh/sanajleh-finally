"""No-op extension stubs for Phase 2+ wiring."""

from __future__ import annotations

from app.core.interfaces.context import ContextProvider, ContextRequest, ContextResponse
from app.core.interfaces.extensions import EvaluationRunner, MemoryStore, TelemetryEmitter
from app.core.interfaces.knowledge import (
    KNOWLEDGE_CONTEXT_PLACEHOLDER,
    KnowledgeRetriever,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from app.core.interfaces.sme import SMERecommendRequest, SMERecommendation, SMEService
from app.schemas.request.package_request import PackageRequest


class NullKnowledgeRetriever:
    """Placeholder until Team Beta Knowledge API is integrated."""

    async def fetch_context(self, request: PackageRequest) -> str:
        return KNOWLEDGE_CONTEXT_PLACEHOLDER

    async def search(self, request: KnowledgeSearchRequest) -> KnowledgeSearchResponse:
        return KnowledgeSearchResponse(results=[], total=0)


class NullContextProvider:
    """Placeholder until Team Beta Context API is integrated."""

    async def get_context(self, request: ContextRequest) -> ContextResponse:
        return ContextResponse()


class NullSMEService:
    """Placeholder until Team Beta SME API is integrated."""

    async def recommend(self, request: SMERecommendRequest) -> list[SMERecommendation]:
        return []


class NullMemoryStore:
    """Placeholder for session memory — Phase 3+."""

    async def get(self, session_id: str) -> dict | None:
        return None

    async def set(self, session_id: str, data: dict) -> None:
        return None


class NullEvaluationRunner:
    """Placeholder for package quality evaluation — Phase 3+."""

    async def evaluate(self, package: dict, request: dict) -> dict:
        return {"score": None, "notes": "Evaluation not configured"}


class NullTelemetryEmitter:
    """Placeholder for observability — Phase 3+."""

    def record_latency(self, operation: str, duration_ms: float, **tags: str) -> None:
        return None

    def record_event(self, event: str, **attributes: str) -> None:
        return None


def assert_protocols() -> None:
    """Verify stubs satisfy future extension protocols."""
    assert isinstance(NullKnowledgeRetriever(), KnowledgeRetriever)
    assert isinstance(NullContextProvider(), ContextProvider)
    assert isinstance(NullSMEService(), SMEService)
    assert isinstance(NullMemoryStore(), MemoryStore)
    assert isinstance(NullEvaluationRunner(), EvaluationRunner)
    assert isinstance(NullTelemetryEmitter(), TelemetryEmitter)
