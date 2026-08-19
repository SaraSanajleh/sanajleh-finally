from datetime import datetime

from app.planning.itinerary import _cost, _minutes, _place, overlay_narrative
from app.retrieval.catalog import load_tourism_catalog
from app.retrieval.knowledge import KnowledgeCard, _card_from_entity
from app.schemas.response.package_response import TourismPackage


def test_visitor_center_clock_matches_catalog_minutes() -> None:
    card = next(c for c in load_tourism_catalog() if c.name == "Wadi Rum Visitor Center")
    assert _minutes(card) == 30
    assert _cost(card) == "5 JOD"
    item, _ = _place(card, datetime(2000, 1, 1, 9, 0), item_type="poi")
    assert item["time"] == "09:00"
    assert item["end_time"] == "09:30"
    assert item["duration_minutes"] == 30
    assert item["estimated_cost"] == "5 JOD"


def test_short_and_long_visits_are_not_clamped() -> None:
    short = KnowledgeCard(
        item_id="poi_short",
        entity_type="poi",
        name="Short stop",
        facts={"visit_minutes": 20, "entry_fee": 5},
    )
    long = KnowledgeCard(
        item_id="poi_long",
        entity_type="poi",
        name="Long hike",
        facts={"visit_minutes": 200, "entry_fee": 0},
    )
    assert _minutes(short) == 20
    assert _minutes(long) == 200
    short_item, _ = _place(short, datetime(2000, 1, 1, 9, 0), item_type="poi")
    long_item, _ = _place(long, datetime(2000, 1, 1, 9, 0), item_type="poi")
    assert short_item["end_time"] == "09:20"
    assert long_item["end_time"] == "12:20"
    assert long_item["estimated_cost"] == "0 JOD"


def test_retriever_flat_facts_keep_minutes_and_price() -> None:
    card = _card_from_entity(
        {
            "id": "poi_flat",
            "name": "Flat POI",
            "facts": {"average_visit_minutes": 45, "entry_fee": 7.5, "currency": "JOD"},
        },
        "poi",
        None,
        "retriever",
    )
    assert card is not None
    assert _minutes(card) == 45
    assert _cost(card) == "7.5 JOD"


def test_retriever_average_visit_minutes_set_the_poi_clock() -> None:
    from app.planning.itinerary import _place
    from app.retrieval.knowledge import overlay_retrieved_evidence

    catalog = KnowledgeCard(
        item_id="poi_avg",
        entity_type="poi",
        name="Canyon Walk",
        facts={"visit_minutes": 60, "entry_fee": 10},
    )
    retrieved = KnowledgeCard(
        item_id="poi_avg",
        entity_type="poi",
        name="Canyon Walk",
        facts={"visit_minutes": 180, "retrieved": True},
        why_retrieved=["retriever"],
    )
    merged = overlay_retrieved_evidence(catalog, retrieved)
    assert _minutes(merged) == 180
    item, _ = _place(merged, datetime(2000, 1, 1, 9, 0), item_type="poi")
    assert item["duration_minutes"] == 180
    assert item["end_time"] == "12:00"


def test_overlay_keeps_catalog_clock_and_price() -> None:
    locked = TourismPackage.model_validate(
        {
            "days": [
                {
                    "day": 1,
                    "region": "Wadi Rum",
                    "schedule": [
                        {
                            "item_id": "poi_002008",
                            "name": "Wadi Rum Visitor Center",
                            "time": "09:00",
                            "end_time": "09:30",
                            "duration_minutes": 30,
                            "estimated_cost": "5 JOD",
                            "description": "catalog",
                        }
                    ],
                }
            ]
        }
    )
    llm = TourismPackage.model_validate(
        {
            "days": [
                {
                    "day": 1,
                    "schedule": [
                        {
                            "item_id": "poi_002008",
                            "name": "Wadi Rum Visitor Center",
                            "time": "11:00",
                            "end_time": "13:00",
                            "duration_minutes": 120,
                            "estimated_cost": "20 JOD",
                            "description": "model wording",
                        }
                    ],
                }
            ]
        }
    )
    merged = overlay_narrative(locked, llm)
    item = merged.days[0].schedule[0]
    assert item.time == "09:00"
    assert item.end_time == "09:30"
    assert item.duration_minutes == 30
    assert item.estimated_cost == "5 JOD"
    assert item.description == "model wording"
