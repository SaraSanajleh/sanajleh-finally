from datetime import datetime

import pytest

from app.context.builder import build_planning_context
from app.planning.geo import catalog_region_key, region_key
from app.planning.profile import normalize_tourist_profile
from app.retrieval.catalog import card_matches_region, cards_for_region
from app.retrieval.composer import compose_trip_knowledge
from app.retrieval.knowledge import KnowledgeCard, _card_from_entity
from app.schemas.request.package_request import PackageRequest
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST


def _minutes_between(end_time: str, start_time: str) -> int:
    end = datetime.strptime(end_time, "%H:%M")
    start = datetime.strptime(start_time, "%H:%M")
    return int((start - end).total_seconds() // 60)


def test_sweimeh_and_dead_sea_region_map_to_dead_sea() -> None:
    assert region_key("Sweimeh") == "dead sea"
    assert region_key("Dead Sea Region") == "dead sea"
    assert catalog_region_key("Sweimeh", "Balqa Governorate") == "dead sea"
    assert catalog_region_key("Ma'in", "Madaba Governorate") == "madaba"


def test_dead_sea_catalog_has_sights_meals_and_hotels() -> None:
    pois = cards_for_region("dead sea", "poi")
    restaurants = cards_for_region("dead sea", "restaurant")
    hotels = cards_for_region("dead sea", "hotel")
    assert pois, "Dead Sea sights exist in the catalog"
    assert restaurants, "Dead Sea restaurants exist in the catalog"
    assert hotels, "Dead Sea hotels exist in the catalog"
    hotel_names = " ".join(card.name.lower() for card in hotels)
    assert "dead sea" in hotel_names or "kempinski" in hotel_names or "mövenpick" in hotel_names


def test_kempinski_dead_sea_matches_dead_sea_day() -> None:
    card = _card_from_entity(
        {
            "id": "hotel_000085",
            "name": "Kempinski Hotel Ishtar Dead Sea",
            "entity_type": "hotel",
            "city": "Sweimeh",
            "region": "Balqa Governorate",
            "category": "Resort",
        },
        "hotel",
        None,
        "catalog",
    )
    assert card is not None
    assert card.region_key == "dead sea"
    assert card_matches_region(card, "dead sea")


def test_irbid_still_cannot_enter_a_dead_sea_day() -> None:
    irbid = KnowledgeCard(
        item_id="poi_irbid",
        entity_type="poi",
        name="Irbid Central Souq",
        city="Irbid",
        region="Irbid Governorate",
        region_key="irbid",
    )
    assert card_matches_region(irbid, "dead sea") is False


@pytest.mark.asyncio
async def test_dead_sea_day_does_not_warn_about_empty_catalog(monkeypatch) -> None:
    async def fake_weather(**kwargs):
        return [], "unavailable"

    monkeypatch.setattr("app.context.builder.fetch_weather", fake_weather)
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "preferredRegions": ["Dead Sea"],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "mustVisit": [],
            "placesToAvoid": "",
        },
        "accommodation": {"type": "hotel", "rating": "4 star"},
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    context = await build_planning_context(profile)
    knowledge = compose_trip_knowledge(
        {"duration_days": 4, "clusters": [], "meta": {"rag_status": "ok"}},
        profile,
        context,
    )
    dead_sea = [item for item in knowledge.day_shortlists if item.region_key == "dead sea"]
    assert dead_sea
    assert dead_sea[0].pois
    assert dead_sea[0].restaurants
    assert any(item.hotels for item in dead_sea)
    assert not any("Dead Sea" in warning for warning in knowledge.warnings)


@pytest.mark.asyncio
async def test_every_exploring_day_keeps_a_full_clock(monkeypatch) -> None:
    async def fake_weather(**kwargs):
        return [], "unavailable"

    monkeypatch.setattr("app.context.builder.fetch_weather", fake_weather)
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "preferredRegions": ["Dead Sea"],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "interests": ["nature", "food", "photography"],
            "mustVisit": [],
            "placesToAvoid": "",
        },
        "accommodation": {"type": "hotel", "rating": "4 star"},
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    context = await build_planning_context(profile)
    knowledge = compose_trip_knowledge(
        {"duration_days": 4, "clusters": [], "meta": {"rag_status": "ok"}},
        profile,
        context,
    )
    from app.planning.itinerary import build_locked_package
    from app.sme.matcher import select_package_smes

    package = build_locked_package(profile, context, knowledge, select_package_smes(profile))
    exploring = [day for day in package.days if not day.is_arrival_day]
    assert len(exploring) == 3
    for day in exploring:
        meals = [item for item in day.schedule if item.type == "restaurant"]
        pois = [item for item in day.schedule if item.type == "poi"]
        transfers = [item for item in day.schedule if item.type == "transfer"]
        assert len(meals) >= 3, day.region
        assert meals[0].time < "10:30"
        assert meals[1].time >= "12:00"
        assert meals[2].time >= "18:00"
        assert len(pois) >= (1 if transfers else 2), (day.region, [item.name for item in pois])
        listed = {
            card.item_id: card.facts.get("visit_minutes")
            for item in knowledge.day_shortlists
            for card in item.pois
        }
        for poi in pois:
            expected = listed.get(poi.item_id)
            if expected in (None, ""):
                continue
            assert poi.duration_minutes == int(round(float(expected))), poi.name
        timed = [item for item in day.schedule if item.type != "hotel" and item.time and item.end_time]
        for left, right in zip(timed, timed[1:]):
            gap = _minutes_between(left.end_time, right.time)
            limit = 180 if right.type == "restaurant" else 90
            assert gap <= limit, (day.region, left.name, right.name, gap)
    madaba = next(day for day in exploring if "madaba" in day.region.lower())
    poi_blob = " ".join(item.name.lower() for item in madaba.schedule if item.type == "poi")
    assert any(token in poi_blob for token in ("george", "nebo", "mosaic", "archaeological"))
    madaba_intent = next(intent for intent in context.day_intents if intent.region_key == "madaba")
    assert madaba_intent.overnight_key == "dead sea"
    first_ds = next(day for day in exploring if "dead sea" in day.region.lower())
    ds_blob = " ".join(item.name.lower() for item in first_ds.schedule if item.type == "poi")
    assert "mount nebo" not in ds_blob
    assert "mosaic map" not in ds_blob
    inland = ("dhiban", "hesban", "king's highway", "kings highway", "la storica")
    for day in exploring:
        if "dead sea" not in day.region.lower() or "madaba" in day.region.lower():
            continue
        blob = " ".join(item.name.lower() for item in day.schedule if item.type == "poi")
        for token in inland:
            assert token not in blob, blob
    assert any(item.type == "transfer" for item in exploring[0].schedule)
