"""Knowledge retrieval contracts — Alpha ↔ Team Beta RAG."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.schemas.request.package_request import PackageRequest

# Soft-fallback when Beta is disabled/unreachable (GitHub Evidence Package path).
KNOWLEDGE_CONTEXT_PLACEHOLDER = (
    "No retrieved knowledge available. Use general Jordan tourism knowledge. "
    "Avoid inventing specific business names unless they are widely known landmarks."
)


@dataclass(frozen=True)
class KnowledgeSearchRequest:
    """Query parameters for knowledge search."""

    query: str
    region: str | None = None
    category: str | None = None
    interests: list[str] | None = None
    max_results: int = 10


@dataclass(frozen=True)
class KnowledgeItem:
    """A single knowledge base result."""

    id: str
    name: str
    category: str
    description: str
    metadata: dict | None = None


@dataclass(frozen=True)
class KnowledgeSearchResponse:
    """Response from knowledge retrieval."""

    results: list[KnowledgeItem]
    total: int


@runtime_checkable
class KnowledgeRetriever(Protocol):
    """Fetch prompt-ready knowledge_context (GitHub Beta HTTP path)."""

    async def fetch_context(self, request: PackageRequest) -> str:
        """Return a string suitable for {{knowledge_context}}."""
        ...


@runtime_checkable
class LegacyKnowledgeSearcher(Protocol):
    """Older search-shaped contract kept for stubs/tests."""

    async def search(self, request: KnowledgeSearchRequest) -> KnowledgeSearchResponse:
        """Search tourism knowledge base."""
        ...
