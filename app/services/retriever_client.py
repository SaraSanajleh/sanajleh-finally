"""HTTP client for Team Beta Retriever (RAG) knowledge search."""

from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable

import httpx

from app.config.settings import AppSettings, get_app_settings
from app.knowledge.planner_assist import build_planning_lock
from app.knowledge.wizard_payload import package_request_to_wizard_payload
from app.schemas.request.package_request import PackageRequest
from app.utils.logging import get_logger

logger = get_logger(__name__)


@runtime_checkable
class TourismKnowledgeProvider(Protocol):
    """Fetches itinerary-shaped RAG context for package generation."""

    async def search_for_itinerary(self, request: PackageRequest) -> dict[str, Any]:
        """Return Retriever SearchResponse-like dict for the LLM prompt."""
        ...

    async def close(self) -> None:
        ...


class NullTourismKnowledgeProvider:
    """No-op provider when RAG is disabled or unreachable."""

    async def search_for_itinerary(self, request: PackageRequest) -> dict[str, Any]:
        return {
            "duration_days": request.duration_days,
            "clusters": [],
            "meta": {"rag_status": "disabled"},
        }

    async def close(self) -> None:
        return None


class HttpRetrieverClient:
    """Calls Team Beta Retriever: POST /api/v1/knowledge/search."""

    def __init__(
        self, settings: AppSettings | None = None, client: httpx.AsyncClient | None = None
    ) -> None:
        self._settings = settings or get_app_settings()
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client

    async def search_for_itinerary(self, request: PackageRequest) -> dict[str, Any]:
        if not self._settings.retriever_enabled:
            return await NullTourismKnowledgeProvider().search_for_itinerary(request)

        payload = package_request_to_wizard_payload(request)
        url = f"{self._settings.retriever_base_url.rstrip('/')}/api/v1/knowledge/search"
        client = await self._get_client()
        try:
            response = await client.post(
                url,
                json=payload,
                timeout=self._settings.retriever_timeout_seconds,
            )
            response.raise_for_status()
            raw = response.json()
            if not isinstance(raw, dict):
                raise ValueError("Retriever returned non-object JSON")

            # Full Retriever payload for cloud LLM — no prune / no fact stripping.
            meta = dict(raw.get("meta") or {})
            meta.update(
                {
                    "rag_status": "ok",
                    "source": "retriever",
                    "compacted": False,
                    "planning_lock": build_planning_lock(raw, request),
                }
            )
            full: dict[str, Any] = {
                "duration_days": raw.get("duration_days"),
                "clusters": list(raw.get("clusters") or []),
                "meta": meta,
            }
            for key, value in raw.items():
                if key not in full:
                    full[key] = value

            logger.info(
                "RAG context loaded (full): clusters=%s duration_days=%s",
                len(full.get("clusters") or []),
                full.get("duration_days"),
            )
            # Debug dump so you can inspect Retriever output after a wizard run.
            try:
                from pathlib import Path

                dump_dir = Path(__file__).resolve().parents[2] / "case_capture"
                dump_dir.mkdir(exist_ok=True)
                dump_path = dump_dir / "last_retriever_response.json"
                dump_path.write_text(
                    json.dumps(full, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                logger.info("RAG dump written: %s", dump_path)
            except Exception as dump_exc:  # noqa: BLE001 — never fail generation on dump
                logger.warning("Could not write RAG dump: %s", dump_exc)
            return full
        except Exception as exc:  # noqa: BLE001 — degrade gracefully for package generation
            logger.warning(
                "Retriever unavailable (%s) — generating without RAG grounding", exc
            )
            return {
                "duration_days": request.duration_days,
                "clusters": [],
                "meta": {"rag_status": "unavailable", "error": str(exc)},
            }

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None


def knowledge_json_for_prompt(knowledge: dict[str, Any]) -> str:
    """Serialize full RAG payload for prompt injection."""
    return json.dumps(knowledge, ensure_ascii=False, separators=(",", ":"))
