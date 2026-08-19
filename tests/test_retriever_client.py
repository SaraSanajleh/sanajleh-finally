"""Tests for Retriever (RAG) client mapping and full-payload pass-through."""

from __future__ import annotations

import pytest

from app.config.settings import AppSettings
from app.schemas.request.package_request import PackageRequest
from app.services.retriever_client import (
    HttpRetrieverClient,
    NullTourismKnowledgeProvider,
    package_request_to_wizard_payload,
)
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST


@pytest.mark.asyncio
async def test_null_provider_returns_empty_clusters() -> None:
    request = PackageRequest.model_validate(VALID_PACKAGE_REQUEST)
    knowledge = await NullTourismKnowledgeProvider().search_for_itinerary(request)
    assert knowledge["clusters"] == []
    assert knowledge["meta"]["rag_status"] == "disabled"


def test_package_request_maps_to_wizard_payload() -> None:
    request = PackageRequest.model_validate(VALID_PACKAGE_REQUEST)
    payload = package_request_to_wizard_payload(request)
    assert payload["duration"] == "5"
    assert payload["adults"] == 2
    assert "history" in payload["interests"]
    assert "Petra" in payload["preferredRegion"]
    assert payload["mustVisit"] == ["Petra", "Dead Sea"]


@pytest.mark.asyncio
async def test_http_client_passes_full_retriever_payload() -> None:
    """Cloud path must not prune POIs/restaurants/hotels from Retriever JSON."""
    raw = {
        "duration_days": 2,
        "clusters": [
            {
                "cluster_id": 0,
                "theme": "Jerash",
                "summary": "full cluster",
                "pois": [
                    {
                        "poi": {
                            "id": f"p{i}",
                            "name": f"POI {i}",
                            "role": "anchor",
                            "facts": {"notes": "x" * 50},
                        },
                        "restaurants": [
                            {"id": f"r{i}{j}", "name": f"R{j}"} for j in range(6)
                        ],
                        "dining_available": True,
                        "distances_to_others": [
                            {"poi_id": f"p{k}", "km": k} for k in range(8)
                        ],
                    }
                    for i in range(6)
                ],
                "hotels": [{"id": f"h{i}", "name": f"H{i}"} for i in range(5)],
                "events": [{"id": f"e{i}", "name": f"E{i}"} for i in range(3)],
            }
        ],
        "meta": {},
    }

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return raw

    class _Client:
        async def post(self, *args: object, **kwargs: object) -> _Resp:
            return _Resp()

    settings = AppSettings(
        retriever_enabled=True,
        retriever_base_url="http://127.0.0.1:8001",
        retriever_timeout_seconds=5.0,
    )
    client = HttpRetrieverClient(settings=settings, client=_Client())  # type: ignore[arg-type]
    request = PackageRequest.model_validate(VALID_PACKAGE_REQUEST)
    out = await client.search_for_itinerary(request)

    cluster = out["clusters"][0]
    assert len(cluster["pois"]) == 6
    assert len(cluster["pois"][0]["restaurants"]) == 6
    assert len(cluster["pois"][0]["distances_to_others"]) == 8
    assert len(cluster["hotels"]) == 5
    assert len(cluster["events"]) == 3
    assert cluster["pois"][0]["poi"]["facts"]["notes"] == "x" * 50
    assert out["meta"]["compacted"] is False
    assert out["meta"]["rag_status"] == "ok"
    assert "planning_lock" in out["meta"]
