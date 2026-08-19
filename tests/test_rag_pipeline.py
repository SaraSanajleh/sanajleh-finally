import pytest

from app.context.builder import build_planning_context
from app.planning.profile import normalize_tourist_profile
from app.retrieval.composer import compose_trip_knowledge
from app.schemas.request.package_request import PackageRequest
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST


def _request() -> PackageRequest:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "preferredRegions": ["Ajloun", "Jerash"],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "interests": ["history", "culture"],
            "mustVisit": ["Jerash"],
            "placesToAvoid": "",
        },
    }
    return PackageRequest.model_validate(payload)


@pytest.mark.asyncio
async def test_retriever_leftovers_cannot_enter_a_jerash_shortlist(monkeypatch) -> None:
    async def fake_weather(**kwargs):
        return [], "unavailable"

    monkeypatch.setattr("app.context.builder.fetch_weather", fake_weather)
    request = _request()
    profile = normalize_tourist_profile(request)
    context = await build_planning_context(profile)
    raw = {
        "duration_days": 3,
        "clusters": [
            {
                "cluster_id": 0,
                "theme": "nearby leftovers",
                "pois": [
                    {
                        "id": "poi_irbid_souq",
                        "name": "Irbid Central Souq",
                        "entity_type": "poi",
                        "region": "Irbid Governorate",
                        "city": "Irbid",
                        "why_retrieved": ["nearby"],
                    }
                ],
                "hotels": [],
            }
        ],
        "meta": {"rag_status": "ok"},
    }
    knowledge = compose_trip_knowledge(raw, profile, context)
    jerash = [item for item in knowledge.day_shortlists if item.region_key == "jerash"]
    assert jerash
    names = [card.name.lower() for item in jerash for card in item.pois]
    assert all("irbid" not in name for name in names)
    assert any("jerash" in card.name.lower() for item in jerash for card in item.pois)


@pytest.mark.asyncio
async def test_amman_overnight_still_gets_hotels_on_a_jerash_day(monkeypatch) -> None:
    async def fake_weather(**kwargs):
        return [], "unavailable"

    monkeypatch.setattr("app.context.builder.fetch_weather", fake_weather)
    request = _request()
    profile = normalize_tourist_profile(request)
    context = await build_planning_context(profile)
    knowledge = compose_trip_knowledge(
        {"duration_days": 3, "clusters": [], "meta": {"rag_status": "unavailable"}},
        profile,
        context,
    )
    assert not any("No listed hotel" in warning for warning in knowledge.warnings)
    arrival = next(item for item in knowledge.day_shortlists if item.region_key == "amman")
    assert arrival.hotels
    assert all("amman" in (card.city or "").lower() or card.region_key == "amman" for card in arrival.hotels)
