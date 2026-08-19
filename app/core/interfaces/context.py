"""Future extension point: Context Engine (weather, maps, opening hours)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ContextRequest:
    """Parameters for contextual enrichment."""

    location: str
    date: str
    places: list[dict[str, str]]


@dataclass(frozen=True)
class ContextResponse:
    """Aggregated contextual data from Team Beta Context API."""

    weather: dict | None = None
    opening_status: list[dict] | None = None
    travel_time: list[dict] | None = None


@runtime_checkable
class ContextProvider(Protocol):
    """Contract for context enrichment — implemented in Phase 2+."""

    async def get_context(self, request: ContextRequest) -> ContextResponse:
        """Fetch weather, travel times, and opening hours."""
        ...
