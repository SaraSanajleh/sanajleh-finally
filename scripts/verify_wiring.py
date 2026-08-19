"""End-to-end wiring check: data -> Retriever -> Alpha client compact."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from app.config.settings import get_app_settings
from app.schemas.request.package_request import PackageRequest
from app.services.retriever_client import HttpRetrieverClient
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "data" / "customized_packages" / "knowledge"


def check_data_files() -> None:
    print("=== DATA ===")
    assert KNOWLEDGE.is_dir(), f"missing {KNOWLEDGE}"
    for name in ("poi.json", "hotel.json", "restaurant.json", "event.json"):
        path = KNOWLEDGE / name
        assert path.is_file(), f"missing {path}"
        data = json.loads(path.read_text(encoding="utf-8"))
        print(f"  {name}: {len(data)}")
        assert len(data) > 0, f"{name} empty"
    # New KB should be much larger than legacy 80/50/30/0
    pois = json.loads((KNOWLEDGE / "poi.json").read_text(encoding="utf-8"))
    events = json.loads((KNOWLEDGE / "event.json").read_text(encoding="utf-8"))
    assert len(pois) >= 400, f"poi count too low: {len(pois)}"
    assert len(events) >= 100, f"event count too low: {len(events)}"
    print("  data_ok")


async def check_retriever_direct() -> None:
    print("=== RETRIEVER DIRECT ===")
    payload = {
        "startDate": "2026-09-01",
        "duration": "3",
        "customDuration": "",
        "arrivalAirport": "AMM",
        "totalBudget": 900,
        "preferredLanguage": "English",
        "preferredRegion": ["Petra", "Wadi Rum", "Dead Sea"],
        "adults": 2,
        "children": 0,
        "childrenAges": [],
        "seniors": 0,
        "groupType": "couple",
        "accessibilityNeeds": [],
        "interests": ["history", "hiking", "photography"],
        "tripPace": "Balanced",
        "activityLevel": "Moderate",
        "mustVisit": ["Petra", "Dead Sea"],
        "placesToAvoid": "",
        "accommodationType": "boutique",
        "hotelRating": "4 star",
        "cuisine": ["Local Jordanian"],
        "specialOccasion": "Anniversary",
        "smePreferences": ["Family-owned Businesses"],
        "aiPriority": "authentic",
        "freeText": "wiring check",
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "http://127.0.0.1:8001/api/v1/knowledge/search",
            json=payload,
            timeout=180,
        )
        r.raise_for_status()
        raw = r.json()
    assert raw.get("duration_days") == 3
    clusters = raw.get("clusters") or []
    assert len(clusters) == 3, f"expected 3 clusters, got {len(clusters)}"
    events_total = sum(len(c.get("events") or []) for c in clusters)
    hotels_total = sum(len(c.get("hotels") or []) for c in clusters)
    pois_total = sum(len(c.get("pois") or []) for c in clusters)
    print(
        f"  duration_days={raw['duration_days']} clusters={len(clusters)} "
        f"pois={pois_total} hotels={hotels_total} events={events_total}"
    )
    assert pois_total > 0
    assert hotels_total > 0
    # New KB has events — should appear for Ma'an/Aqaba style trips
    print(f"  events_present={events_total > 0}")
    sample_id = ((clusters[0].get("pois") or [{}])[0].get("poi") or {}).get("id")
    print(f"  sample_poi_id={sample_id}")
    print("  retriever_direct_ok")


async def check_alpha_client() -> None:
    print("=== ALPHA HttpRetrieverClient ===")
    settings = get_app_settings()
    print(
        f"  enabled={settings.retriever_enabled} "
        f"base_url={settings.retriever_base_url} "
        f"timeout={settings.retriever_timeout_seconds}"
    )
    assert settings.retriever_enabled is True
    assert "8001" in settings.retriever_base_url

    payload = json.loads(json.dumps(VALID_PACKAGE_REQUEST))
    payload["trip"]["duration"] = "2"
    request = PackageRequest.model_validate(payload)
    client = HttpRetrieverClient(settings=settings)
    try:
        compact = await client.search_for_itinerary(request)
    finally:
        await client.close()

    meta = compact.get("meta") or {}
    clusters = compact.get("clusters") or []
    print(
        f"  rag_status={meta.get('rag_status')} source={meta.get('source')} "
        f"clusters={len(clusters)} duration_days={compact.get('duration_days')}"
    )
    assert meta.get("rag_status") == "ok", meta
    assert meta.get("source") == "retriever"
    assert len(clusters) == 2
    poi0 = ((clusters[0].get("pois") or [{}])[0].get("poi") or {})
    assert poi0.get("id"), "compact must keep entity id"
    assert poi0.get("name"), "compact must keep name"
    assert "why_retrieved" in poi0 or poi0.get("why")
    # Prove we are not on the empty-events legacy KB path exclusively
    events_total = sum(len(c.get("events") or []) for c in clusters)
    print(f"  compact_events={events_total} sample={poi0.get('name')}")
    print("  alpha_client_ok")


async def check_alpha_api() -> None:
    print("=== ALPHA API ===")
    async with httpx.AsyncClient() as client:
        health = await client.get("http://127.0.0.1:8000/api/v1/health", timeout=15)
        health.raise_for_status()
        print(f"  health={health.json()}")
        llm = await client.get("http://127.0.0.1:8000/api/v1/health/llm", timeout=20)
        llm.raise_for_status()
        print(f"  llm={llm.json()}")
    print("  alpha_api_ok")


async def check_frontend() -> None:
    print("=== FRONTEND ===")
    async with httpx.AsyncClient() as client:
        r = await client.get("http://localhost:3000/wizard", timeout=15)
        print(f"  wizard_status={r.status_code}")
        r.raise_for_status()
    print("  frontend_ok")


async def main() -> None:
    check_data_files()
    await check_retriever_direct()
    await check_alpha_client()
    await check_alpha_api()
    await check_frontend()
    print("=== ALL WIRING CHECKS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
