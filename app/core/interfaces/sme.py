"""Future extension point: SME recommendation service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class SMERecommendRequest:
    """Parameters for SME/guide recommendation."""

    language: str
    tour_type: str
    interest: str
    region: str


@dataclass(frozen=True)
class SMERecommendation:
    """A recommended SME (guide, operator, etc.)."""

    id: str
    name: str
    match_score: float
    reason: str
    metadata: dict | None = None


@runtime_checkable
class SMEService(Protocol):
    """Contract for SME recommendations — implemented in Phase 2+."""

    async def recommend(self, request: SMERecommendRequest) -> list[SMERecommendation]:
        """Return ranked SME recommendations."""
        ...
