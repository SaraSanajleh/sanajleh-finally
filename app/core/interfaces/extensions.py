"""Future extension points: memory, evaluation, observability."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MemoryStore(Protocol):
    """Contract for conversation/session memory — Phase 3+."""

    async def get(self, session_id: str) -> dict[str, Any] | None:
        ...

    async def set(self, session_id: str, data: dict[str, Any]) -> None:
        ...


@runtime_checkable
class EvaluationRunner(Protocol):
    """Contract for package quality evaluation — Phase 3+."""

    async def evaluate(self, package: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
        ...


@runtime_checkable
class TelemetryEmitter(Protocol):
    """Contract for observability and metrics — Phase 3+."""

    def record_latency(self, operation: str, duration_ms: float, **tags: str) -> None:
        ...

    def record_event(self, event: str, **attributes: str) -> None:
        ...
