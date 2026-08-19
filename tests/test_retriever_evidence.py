import pytest

from datetime import datetime

from app.context.builder import build_planning_context
from app.planning.itinerary import _minutes, _place
from app.planning.profile import normalize_tourist_profile
from app.retrieval.composer import compose_trip_knowledge
from app.retrieval.knowledge import KnowledgeCard, compress_knowledge
from app.retrieval.query import DayRetrievalQuery
from app.retrieval.ranker import score_card
from app.schemas.request.package_request import PackageRequest
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST


def _rum_profile():
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "preferredRegions": ["Petra", "Wadi Rum"],
            "arrivalTime": "14:00",
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "interests": ["history", "nature", "photography"],
            "mustVisit": ["Petra", "Wadi Rum"],
            "placesToAvoid": "",
        },
    }
    return normalize_tourist_profile(PackageRequest.model_validate(payload))


def _query() -> DayRetrievalQuery:
    return DayRetrievalQuery.model_validate(
        {
            "day": 3,
            "region": "Wadi Rum",
            "region_key": "wadi rum",
            "theme": "Wadi Rum",
            "is_must_visit": True,
            "sights": 3,
            "meals": 2,
            "interests": ["history", "nature", "photography"],
        }
    )


RETRIEVER_SAMPLE = {
    "duration_days": 3,
    "clusters": [
        {
            "cluster_id": 0,
            "theme": "Ma'an Governorate · history, nature, photography",
            "pois": [
                {
                    "poi": {
                        "id": "poi_002005",
                        "name": "Petra Museum",
                        "city": "Wadi Musa",
                        "region": "Ma'an Governorate",
                        "latitude": 30.32525,
                        "longitude": 35.468222,
                        "why_retrieved": ["matches history interest"],
                        "facts": {
                            "category": "Museum",
                            "average_visit_minutes": 60,
                            "opening_hours": "08:30",
                            "closing_hours": "18:30",
                            "entry_fee": 0,
                            "currency": "JOD",
                            "indoor_outdoor": "Indoor",
                            "highlights": ["Over 280 original archaeological artifacts on display"],
                        },
                    },
                    "restaurants": [
                        {
                            "id": "restaurant_002003",
                            "name": "My Mom's Recipe Restaurant",
                            "city": "Wadi Musa",
                            "region": "Ma'an Governorate",
                            "latitude": 30.32481,
                            "longitude": 35.4682,
                            "why_retrieved": ["~49 m away"],
                            "facts": {
                                "average_cost_per_person": 10,
                                "average_dining_minutes": 75,
                                "opening_hours": "11:00",
                                "cuisine_types": ["Jordanian"],
                            },
                        }
                    ],
                    "distances_to_others": [{"poi_id": "poi_002006", "km": 1.8}],
                },
                {
                    "poi": {
                        "id": "poi_002011",
                        "name": "Um Frouth Rock Bridge",
                        "role": "anchor",
                        "city": "Wadi Rum",
                        "region": "Ma'an Governorate",
                        "latitude": 29.462778,
                        "longitude": 35.437778,
                        "why_retrieved": ["matches nature interest", "matches photography interest"],
                        "facts": {
                            "category": "Nature",
                            "subcategory": "Natural Arch",
                            "themes": ["Geology", "Desert", "Photography"],
                            "average_visit_minutes": 40,
                            "entry_fee": 5,
                            "currency": "JOD",
                            "indoor_outdoor": "Outdoor",
                            "highlights": ["20-meter high natural sandstone bridge"],
                        },
                    },
                    "restaurants": [
                        {
                            "id": "restaurant_002057",
                            "name": "Rahayeb Desert Camp Restaurant",
                            "city": "Wadi Rum",
                            "region": "Ma'an Governorate",
                            "latitude": 29.542,
                            "longitude": 35.431,
                            "why_retrieved": ["~8.8 km away"],
                            "facts": {"average_cost_per_person": 11, "cuisine_types": ["Jordanian"]},
                        }
                    ],
                    "distances_to_others": [{"poi_id": "poi_002010", "km": 3.7}],
                },
                {
                    "poi": {
                        "id": "poi_002009",
                        "name": "Lawrence's Spring",
                        "role": "anchor",
                        "city": "Wadi Rum",
                        "region": "Ma'an Governorate",
                        "latitude": 29.565833,
                        "longitude": 35.418056,
                        "why_retrieved": [
                            "matches history interest",
                            "matches nature interest",
                            "matches photography interest",
                        ],
                        "facts": {
                            "category": "Nature",
                            "average_visit_minutes": 45,
                            "entry_fee": 5,
                            "indoor_outdoor": "Outdoor",
                        },
                    },
                    "restaurants": [
                        {
                            "id": "restaurant_007075",
                            "name": "Wadi Rum Visitor Center Rest House",
                            "city": "Wadi Rum",
                            "region": "Ma'an Governorate",
                            "latitude": 29.5778,
                            "longitude": 35.419,
                            "facts": {"average_cost_per_person": 7},
                        }
                    ],
                    "distances_to_others": [{"poi_id": "poi_002032", "km": 2.6}],
                },
                {
                    "poi": {
                        "id": "poi_002032",
                        "name": "Red Sand Dunes of Wadi Rum",
                        "role": "anchor",
                        "city": "Wadi Rum",
                        "region": "Ma'an Governorate",
                        "latitude": 29.585278,
                        "longitude": 35.433611,
                        "why_retrieved": ["matches nature interest"],
                        "facts": {
                            "category": "Nature",
                            "subcategory": "Sand Dune",
                            "average_visit_minutes": 45,
                            "entry_fee": 5,
                            "indoor_outdoor": "Outdoor",
                        },
                    },
                    "restaurants": [],
                    "distances_to_others": [{"poi_id": "poi_002009", "km": 2.6}],
                },
            ],
        }
    ],
    "meta": {"rag_status": "ok"},
}


def test_compress_keeps_nearby_restaurants_and_distances() -> None:
    profile = _rum_profile()
    recalled = compress_knowledge(RETRIEVER_SAMPLE, profile)
    um = next(card for card in recalled.pois if card.item_id == "poi_002011")
    assert um.facts.get("retrieved") is True
    assert "restaurant_002057" in (um.facts.get("nearby_restaurant_ids") or [])
    assert (um.facts.get("nearby_poi_km") or {}).get("poi_002010") == 3.7
    assert _minutes(um) == 40
    rest_names = {card.name for card in recalled.restaurants}
    assert "Rahayeb Desert Camp Restaurant" in rest_names
    assert "My Mom's Recipe Restaurant" in rest_names


def test_retrieved_desert_stop_beats_visitor_center() -> None:
    profile = _rum_profile()
    query = _query()
    visitor = KnowledgeCard(
        item_id="poi_002008",
        entity_type="poi",
        name="Wadi Rum Visitor Center",
        city="Wadi Rum",
        region="Ma'an Governorate",
        region_key="wadi rum",
        category="Nature",
        facts={"subcategory": "Protected Area Headquarters", "visit_minutes": 30},
    )
    um = KnowledgeCard(
        item_id="poi_002011",
        entity_type="poi",
        name="Um Frouth Rock Bridge",
        city="Wadi Rum",
        region="Ma'an Governorate",
        region_key="wadi rum",
        category="Nature",
        why_retrieved=["matches nature interest", "matches photography interest"],
        facts={
            "retrieved": True,
            "retrieval_rank": 1,
            "role": "anchor",
            "subcategory": "Natural Arch",
            "themes": ["Desert", "Photography"],
            "visit_minutes": 40,
        },
    )
    ranked_um = score_card(um, profile, query)
    ranked_visitor = score_card(visitor, profile, query)
    assert ranked_um is not None and ranked_visitor is not None
    assert ranked_um.relevance > ranked_visitor.relevance


@pytest.mark.asyncio
async def test_wadi_rum_shortlist_prefers_retrieved_sights(monkeypatch) -> None:
    async def fake_weather(**kwargs):
        return [], "unavailable"

    monkeypatch.setattr("app.context.builder.fetch_weather", fake_weather)
    profile = _rum_profile()
    context = await build_planning_context(profile)
    knowledge = compose_trip_knowledge(RETRIEVER_SAMPLE, profile, context)
    rum = next(item for item in knowledge.day_shortlists if item.region_key == "wadi rum")
    names = [card.name for card in rum.pois]
    assert "Um Frouth Rock Bridge" in names
    assert names[0] != "Wadi Rum Visitor Center"
    assert any("Lawrence" in name or "Dune" in name or "Frouth" in name for name in names[:3])
    rest_names = [card.name for card in rum.restaurants]
    assert any("Rahayeb" in name or "Rest House" in name for name in rest_names)
    petra = next(item for item in knowledge.day_shortlists if item.region_key == "petra")
    petra_names = [card.name for card in petra.pois]
    assert "Petra Museum" in petra_names or any("petra" in name.lower() for name in petra_names)
    um = next(card for card in rum.pois if "Frouth" in card.name)
    item, _ = _place(um, datetime(2000, 1, 1, 9, 0), item_type="poi")
    assert item["duration_minutes"] == 40
    assert item["estimated_cost"] == "5 JOD"
    assert item["end_time"] == "09:40"
