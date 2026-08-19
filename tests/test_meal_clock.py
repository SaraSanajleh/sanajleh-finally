from datetime import datetime

from app.context.models import DayIntent
from app.planning.itinerary import _build_day
from app.planning.profile import normalize_tourist_profile
from app.retrieval.knowledge import DayShortlist, KnowledgeCard
from app.schemas.request.package_request import PackageRequest
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST


def _card(
    item_id: str,
    name: str,
    entity: str,
    minutes: int,
    opens: str,
    closes: str,
    category: str = "",
    region_key: str = "",
    city: str = "City",
    region: str = "Region",
) -> KnowledgeCard:
    return KnowledgeCard(
        item_id=item_id,
        entity_type=entity,
        name=name,
        city=city,
        region=region,
        region_key=region_key,
        category=category,
        facts={
            "visit_minutes": minutes,
            "opening_hours": opens,
            "closing_hours": closes,
        },
    )


def test_full_day_eats_breakfast_lunch_and_dinner() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {**VALID_PACKAGE_REQUEST["trip"], "duration": "3", "preferredRegions": ["Aqaba"]},
        "preferences": {**VALID_PACKAGE_REQUEST["preferences"], "mustVisit": [], "placesToAvoid": ""},
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    intent = DayIntent(
        day=2,
        date="2025-08-16",
        region="Aqaba",
        region_key="aqaba",
        theme="Aqaba",
        sights=3,
        meals=3,
    )
    shortlist = DayShortlist(
        day=2,
        region="Aqaba",
        region_key="aqaba",
        pois=[
            _card("p1", "Old Church", "poi", 30, "08:30", "17:00"),
            _card("p2", "Marina Walk", "poi", 120, "09:00", "18:00"),
            _card("p3", "Town Mosque", "poi", 30, "08:00", "20:00"),
        ],
        restaurants=[
            _card("r1", "Morning Cafe", "restaurant", 45, "07:30", "15:00", "Cafe"),
            _card("r2", "Harbour Grill", "restaurant", 90, "12:00", "23:00", "Restaurant"),
            _card("r3", "Evening Kitchen", "restaurant", 60, "17:00", "23:00", "Restaurant"),
        ],
    )
    day = _build_day(
        intent,
        shortlist,
        include_hotel=False,
        check_in=False,
        heat=False,
        used_ids=set(),
        airport="AMM",
        profile=profile,
        stay_notes=[],
    )
    meals = [item for item in day["schedule"] if item["type"] == "restaurant"]
    pois = [item for item in day["schedule"] if item["type"] == "poi"]
    assert [item["name"] for item in meals] == ["Morning Cafe", "Harbour Grill", "Evening Kitchen"]
    assert all((item.get("duration_minutes") or 0) <= 60 for item in meals)
    assert meals[1]["duration_minutes"] == 60
    assert meals[0]["time"] < "10:00"
    assert meals[1]["time"] >= "12:00"
    assert meals[2]["time"] >= "18:00"
    assert pois
    assert pois[0]["time"] >= meals[0]["end_time"]
    assert any(item["time"] >= meals[1]["end_time"] and item["time"] < meals[2]["time"] for item in pois)


def _minutes_between(end_time: str, start_time: str) -> int:
    end = datetime.strptime(end_time, "%H:%M")
    start = datetime.strptime(start_time, "%H:%M")
    return int((start - end).total_seconds() // 60)


def test_day_does_not_leave_a_long_empty_gap() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {**VALID_PACKAGE_REQUEST["trip"], "duration": "3", "preferredRegions": ["Wadi Rum"]},
        "preferences": {**VALID_PACKAGE_REQUEST["preferences"], "mustVisit": [], "placesToAvoid": ""},
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    intent = DayIntent(
        day=2,
        date="2025-08-21",
        region="Wadi Rum",
        region_key="wadi rum",
        theme="Wadi Rum",
        sights=3,
        meals=3,
        overnight_key="wadi rum",
        overnight_region="Wadi Rum",
    )
    shortlist = DayShortlist(
        day=2,
        region="Wadi Rum",
        region_key="wadi rum",
        pois=[
            _card("p1", "Spring", "poi", 45, "08:00", "18:00"),
            _card("p2", "Fort Ruins", "poi", 25, "08:00", "18:00"),
            _card("p3", "Petroglyphs", "poi", 35, "08:00", "18:00"),
            _card("p4", "Sand Dunes", "poi", 90, "08:00", "18:00"),
            _card("p5", "Canyon Walk", "poi", 80, "08:00", "18:00"),
            _card("p6", "Rock Bridge", "poi", 50, "08:00", "18:00"),
            _card("p7", "Sunset Dune", "poi", 40, "08:00", "18:00"),
        ],
        restaurants=[
            _card("r1", "Camp Breakfast", "restaurant", 45, "07:00", "11:00", "Cafe"),
            _card("r2", "Camp Lunch", "restaurant", 70, "12:00", "16:00", "Restaurant"),
            _card("r3", "Camp Dinner", "restaurant", 90, "17:00", "22:00", "Restaurant"),
        ],
    )
    day = _build_day(
        intent,
        shortlist,
        include_hotel=False,
        check_in=False,
        heat=True,
        used_ids=set(),
        airport="AMM",
        profile=profile,
        stay_notes=[],
    )
    items = [item for item in day["schedule"] if item["type"] != "hotel"]
    types = [item["type"] for item in items]
    assert "poi" in types
    for left, right in zip(items, items[1:]):
        assert not (left["type"] == "restaurant" and right["type"] == "restaurant")
        gap = _minutes_between(left["end_time"], right["time"])
        assert gap <= 90, (left["name"], right["name"], gap)
    meals = [item for item in items if item["type"] == "restaurant"]
    assert meals[0]["time"] < "10:00"
    assert "12:00" <= meals[1]["time"] <= "14:30"
    assert meals[2]["time"] >= "18:00"


def test_lunch_skips_a_closed_cafe_and_still_serves_three_meals() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {**VALID_PACKAGE_REQUEST["trip"], "duration": "3", "preferredRegions": ["Madaba"]},
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "interests": ["religious_sites", "museums"],
            "mustVisit": [],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    intent = DayIntent(
        day=2,
        date="2026-08-21",
        region="Karak",
        region_key="karak",
        theme="Karak",
        sights=3,
        meals=3,
        overnight_key="karak",
        overnight_region="Karak",
    )
    shortlist = DayShortlist(
        day=2,
        region="Karak",
        region_key="karak",
        pois=[
            _card("p1", "Karak Castle", "poi", 90, "08:00", "17:00"),
            _card("p2", "St George Church", "poi", 30, "08:00", "17:00"),
            _card("p3", "City Museum", "poi", 60, "09:00", "17:00"),
        ],
        restaurants=[
            _card("r1", "Morning Cafe", "restaurant", 45, "07:30", "11:00", "Cafe"),
            _card("r2", "Castle Lunch", "restaurant", 60, "12:00", "16:00", "Restaurant"),
            _card("r3", "Evening Kitchen", "restaurant", 60, "17:00", "23:00", "Restaurant"),
        ],
    )
    day = _build_day(
        intent,
        shortlist,
        include_hotel=False,
        check_in=False,
        heat=False,
        used_ids=set(),
        airport="AMM",
        profile=profile,
        stay_notes=[],
    )
    meals = [item for item in day["schedule"] if item["type"] == "restaurant"]
    pois = [item for item in day["schedule"] if item["type"] == "poi"]
    assert [item["name"] for item in meals] == ["Morning Cafe", "Castle Lunch", "Evening Kitchen"]
    assert meals[1]["time"] >= "12:00"
    assert meals[2]["time"] >= "18:00"
    assert {item["name"] for item in pois} <= {"Karak Castle", "St George Church", "City Museum"}


def test_end_of_day_hotel_has_no_clock() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {**VALID_PACKAGE_REQUEST["trip"], "duration": "3", "preferredRegions": ["Aqaba"]},
        "preferences": {**VALID_PACKAGE_REQUEST["preferences"], "mustVisit": [], "placesToAvoid": ""},
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    intent = DayIntent(
        day=2,
        date="2025-08-16",
        region="Aqaba",
        region_key="aqaba",
        theme="Aqaba",
        sights=3,
        meals=3,
        overnight_key="aqaba",
        overnight_region="Aqaba",
    )
    hotel = KnowledgeCard(
        item_id="h1",
        entity_type="hotel",
        name="Harbour Hotel",
        city="Aqaba",
        region="Aqaba",
        region_key="aqaba",
        facts={"night_price": 80, "star_rating": 4},
    )
    day = _build_day(
        intent,
        DayShortlist(
            day=2,
            region="Aqaba",
            region_key="aqaba",
            pois=[_card("p1", "Fort", "poi", 60, "08:00", "18:00")],
            restaurants=[
                _card("r1", "Morning Cafe", "restaurant", 45, "07:00", "11:00", "Cafe"),
                _card("r2", "Harbour Grill", "restaurant", 70, "12:00", "16:00", "Restaurant"),
                _card("r3", "Evening Kitchen", "restaurant", 90, "17:00", "23:00", "Restaurant"),
            ],
            hotels=[hotel],
        ),
        include_hotel=True,
        check_in=True,
        heat=False,
        used_ids=set(),
        airport="AMM",
        profile=profile,
        stay_notes=[],
    )
    stays = [item for item in day["schedule"] if item["type"] == "hotel"]
    assert stays
    assert stays[-1]["name"] == "Harbour Hotel"
    assert stays[-1]["time"] == ""
    assert stays[-1]["end_time"] == ""
    assert day["schedule"][-1]["type"] == "hotel"


def test_later_days_still_get_breakfast_lunch_and_dinner() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {**VALID_PACKAGE_REQUEST["trip"], "duration": "3", "preferredRegions": ["Aqaba"]},
        "preferences": {**VALID_PACKAGE_REQUEST["preferences"], "mustVisit": [], "placesToAvoid": ""},
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    intent = DayIntent(
        day=2,
        date="2025-08-16",
        region="Aqaba",
        region_key="aqaba",
        theme="Aqaba",
        sights=3,
        meals=3,
    )
    shortlist = DayShortlist(
        day=2,
        region="Aqaba",
        region_key="aqaba",
        pois=[
            _card("p1", "Old Church", "poi", 30, "08:30", "17:00"),
            _card("p2", "Marina Walk", "poi", 90, "09:00", "18:00"),
            _card("p3", "Town Mosque", "poi", 30, "08:00", "20:00"),
        ],
        restaurants=[
            _card("r1", "Morning Cafe", "restaurant", 45, "07:30", "15:00", "Cafe"),
            _card("r2", "Harbour Grill", "restaurant", 90, "12:00", "23:00", "Restaurant"),
            _card("r3", "Evening Kitchen", "restaurant", 60, "17:00", "23:00", "Restaurant"),
        ],
    )
    used = {"r1", "r2", "r3"}
    day = _build_day(
        intent,
        shortlist,
        include_hotel=False,
        check_in=False,
        heat=False,
        used_ids=used,
        airport="AMM",
        profile=profile,
        stay_notes=[],
    )
    meals = [item for item in day["schedule"] if item["type"] == "restaurant"]
    assert [item["name"] for item in meals] == ["Morning Cafe", "Harbour Grill", "Evening Kitchen"]
    assert meals[0]["time"] < "10:00"
    assert meals[1]["time"] >= "12:00"
    assert meals[2]["time"] >= "18:00"


def test_busy_morning_still_gets_lunch_before_afternoon() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {**VALID_PACKAGE_REQUEST["trip"], "duration": "3", "preferredRegions": ["Aqaba"]},
        "preferences": {**VALID_PACKAGE_REQUEST["preferences"], "mustVisit": [], "placesToAvoid": ""},
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    intent = DayIntent(
        day=2,
        date="2025-08-16",
        region="Aqaba",
        region_key="aqaba",
        theme="Aqaba",
        sights=3,
        meals=3,
        overnight_key="aqaba",
        overnight_region="Aqaba",
    )
    shortlist = DayShortlist(
        day=2,
        region="Aqaba",
        region_key="aqaba",
        pois=[
            _card("p1", "Fortress", "poi", 120, "08:00", "18:00"),
            _card("p2", "Old Town", "poi", 60, "08:00", "18:00"),
            _card("p3", "South Beach", "poi", 90, "08:00", "18:00"),
            _card("p4", "Marina Walk", "poi", 60, "08:00", "18:00"),
        ],
        restaurants=[
            _card("r1", "Morning Cafe", "restaurant", 45, "07:30", "15:00", "Cafe"),
            _card("r2", "Harbour Grill", "restaurant", 80, "12:00", "16:00", "Restaurant"),
            _card("r3", "Evening Kitchen", "restaurant", 90, "17:00", "23:00", "Restaurant"),
        ],
    )
    day = _build_day(
        intent,
        shortlist,
        include_hotel=False,
        check_in=False,
        heat=False,
        used_ids=set(),
        airport="AMM",
        profile=profile,
        stay_notes=[],
    )
    meals = [item for item in day["schedule"] if item["type"] == "restaurant"]
    pois = [item for item in day["schedule"] if item["type"] == "poi"]
    assert len(meals) == 3
    assert meals[1]["name"] == "Harbour Grill"
    assert meals[1]["time"] >= "12:00"
    assert any(item["time"] < meals[1]["time"] for item in pois)
    assert any(item["time"] >= meals[1]["end_time"] for item in pois)
    assert meals[2]["time"] >= "18:00"


def test_same_restaurant_name_is_not_used_twice_on_one_day() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {**VALID_PACKAGE_REQUEST["trip"], "duration": "3", "preferredRegions": ["Aqaba"]},
        "preferences": {**VALID_PACKAGE_REQUEST["preferences"], "mustVisit": [], "placesToAvoid": ""},
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    intent = DayIntent(
        day=2,
        date="2025-08-16",
        region="Aqaba",
        region_key="aqaba",
        theme="Aqaba",
        sights=2,
        meals=3,
    )
    shortlist = DayShortlist(
        day=2,
        region="Aqaba",
        region_key="aqaba",
        pois=[
            _card("p1", "Old Church", "poi", 45, "08:30", "17:00"),
            _card("p2", "Marina Walk", "poi", 60, "09:00", "18:00"),
        ],
        restaurants=[
            _card("r1", "Morning Cafe", "restaurant", 45, "07:30", "15:00", "Cafe"),
            _card("r2", "Panorama Restaurant", "restaurant", 90, "12:00", "23:00", "Restaurant"),
            _card("r3", "Panorama Restaurant", "restaurant", 90, "12:00", "23:00", "Restaurant"),
            _card("r4", "Harbour Grill", "restaurant", 60, "17:00", "23:00", "Restaurant"),
        ],
    )
    day = _build_day(
        intent,
        shortlist,
        include_hotel=False,
        check_in=False,
        heat=False,
        used_ids=set(),
        airport="AMM",
        profile=profile,
        stay_notes=[],
    )
    meals = [item for item in day["schedule"] if item["type"] == "restaurant"]
    names = [item["name"] for item in meals]
    assert len(names) == len(set(names))
    assert "Harbour Grill" in names


def test_breakfast_is_served_even_when_listings_open_at_noon() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {**VALID_PACKAGE_REQUEST["trip"], "duration": "3", "preferredRegions": ["Aqaba"]},
        "preferences": {**VALID_PACKAGE_REQUEST["preferences"], "mustVisit": [], "placesToAvoid": ""},
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    intent = DayIntent(
        day=2,
        date="2025-08-16",
        region="Aqaba",
        region_key="aqaba",
        theme="Aqaba",
        sights=2,
        meals=3,
    )
    shortlist = DayShortlist(
        day=2,
        region="Aqaba",
        region_key="aqaba",
        pois=[
            _card("p1", "Old Church", "poi", 45, "08:30", "17:00"),
            _card("p2", "Marina Walk", "poi", 60, "09:00", "18:00"),
        ],
        restaurants=[
            _card("r1", "Resort Kitchen", "restaurant", 60, "12:00", "23:00", "Restaurant"),
            _card("r2", "Harbour Grill", "restaurant", 90, "12:00", "23:00", "Restaurant"),
            _card("r3", "Evening Kitchen", "restaurant", 60, "17:00", "23:00", "Restaurant"),
        ],
    )
    day = _build_day(
        intent,
        shortlist,
        include_hotel=False,
        check_in=False,
        heat=False,
        used_ids=set(),
        airport="AMM",
        profile=profile,
        stay_notes=[],
    )
    meals = [item for item in day["schedule"] if item["type"] == "restaurant"]
    assert len(meals) >= 3
    assert meals[0]["time"] < "10:30"
    assert meals[1]["time"] >= "12:00"
    assert meals[2]["time"] >= "18:00"


def test_same_kitchen_name_is_not_used_for_breakfast_and_lunch() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {**VALID_PACKAGE_REQUEST["trip"], "duration": "3", "preferredRegions": ["Madaba"]},
        "preferences": {**VALID_PACKAGE_REQUEST["preferences"], "mustVisit": [], "placesToAvoid": ""},
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    intent = DayIntent(
        day=2,
        date="2026-08-23",
        region="Madaba",
        region_key="madaba",
        theme="Madaba",
        sights=2,
        meals=3,
        overnight_key="madaba",
        overnight_region="Madaba",
    )
    shortlist = DayShortlist(
        day=2,
        region="Madaba",
        region_key="madaba",
        pois=[
            _card("p1", "Mount Nebo", "poi", 90, "08:00", "17:00", region_key="madaba", city="Madaba"),
            _card("p2", "Archaeological Park", "poi", 60, "08:00", "17:00", region_key="madaba", city="Madaba"),
        ],
        restaurants=[
            _card("r1", "Al-Bustan", "restaurant", 45, "07:30", "23:00", "Cafe", region_key="madaba", city="Madaba"),
            _card("r2", "Al-Bustan Restaurant Madaba", "restaurant", 90, "12:00", "23:00", "Restaurant", region_key="madaba", city="Madaba"),
            _card("r3", "Haret Jdoudna", "restaurant", 60, "12:00", "23:00", "Restaurant", region_key="madaba", city="Madaba"),
        ],
    )
    day = _build_day(
        intent,
        shortlist,
        include_hotel=False,
        check_in=False,
        heat=False,
        used_ids=set(),
        airport="AMM",
        profile=profile,
        stay_notes=[],
    )
    meals = [item for item in day["schedule"] if item["type"] == "restaurant"]
    stems = {item["name"].split()[0].lower() for item in meals[:2]}
    assert len(meals) >= 3
    assert "haret jdoudna" in {item["name"].lower() for item in meals}


def test_dinner_still_appears_when_only_two_kitchens_are_listed() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {**VALID_PACKAGE_REQUEST["trip"], "duration": "3", "preferredRegions": ["Aqaba"]},
        "preferences": {**VALID_PACKAGE_REQUEST["preferences"], "mustVisit": [], "placesToAvoid": ""},
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    intent = DayIntent(
        day=2,
        date="2026-08-22",
        region="Aqaba",
        region_key="aqaba",
        theme="Aqaba",
        sights=2,
        meals=3,
        overnight_key="aqaba",
        overnight_region="Aqaba",
    )
    shortlist = DayShortlist(
        day=2,
        region="Aqaba",
        region_key="aqaba",
        pois=[
            _card("p1", "Fort", "poi", 60, "08:00", "18:00", region_key="aqaba", city="Aqaba"),
            _card("p2", "South Beach", "poi", 90, "08:00", "18:00", region_key="aqaba", city="Aqaba"),
        ],
        restaurants=[
            _card("r1", "Morning Cafe", "restaurant", 45, "07:00", "11:00", "Cafe", region_key="aqaba", city="Aqaba"),
            _card("r2", "Harbour Grill", "restaurant", 70, "12:00", "23:00", "Restaurant", region_key="aqaba", city="Aqaba"),
        ],
    )
    day = _build_day(
        intent,
        shortlist,
        include_hotel=False,
        check_in=False,
        heat=False,
        used_ids=set(),
        airport="AMM",
        profile=profile,
        stay_notes=[],
    )
    meals = [item for item in day["schedule"] if item["type"] == "restaurant"]
    assert len(meals) == 3
    assert meals[2]["time"] >= "18:00"


def test_waking_far_away_puts_the_drive_on_the_clock() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "arrivalAirport": "AQJ",
            "preferredRegions": ["Dead Sea"],
        },
        "preferences": {**VALID_PACKAGE_REQUEST["preferences"], "mustVisit": [], "placesToAvoid": ""},
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    intent = DayIntent(
        day=2,
        date="2026-08-21",
        region="Dead Sea",
        region_key="dead sea",
        theme="Dead Sea",
        sights=3,
        meals=3,
        overnight_key="dead sea",
        overnight_region="Dead Sea",
    )
    shortlist = DayShortlist(
        day=2,
        region="Dead Sea",
        region_key="dead sea",
        pois=[
            _card("p1", "Dead Sea Panorama Complex", "poi", 90, "08:00", "18:00", region_key="dead sea", city="Sweimeh"),
            _card("p2", "Wadi Mujib", "poi", 120, "08:00", "17:00", region_key="dead sea", city="Sweimeh"),
        ],
        restaurants=[
            _card("r1", "Tala Bay Cafe", "restaurant", 45, "07:00", "11:00", "Cafe", region_key="aqaba", city="Aqaba"),
            _card("r2", "Panorama Restaurant", "restaurant", 70, "12:00", "16:00", "Restaurant", region_key="dead sea", city="Sweimeh"),
            _card("r3", "Il Terrazzo", "restaurant", 90, "18:00", "23:00", "Restaurant", region_key="dead sea", city="Sweimeh"),
        ],
    )
    day = _build_day(
        intent,
        shortlist,
        include_hotel=False,
        check_in=False,
        heat=False,
        used_ids=set(),
        airport="AQJ",
        profile=profile,
        stay_notes=[],
        from_key="aqaba",
    )
    types = [item["type"] for item in day["schedule"]]
    meals = [item for item in day["schedule"] if item["type"] == "restaurant"]
    pois = [item for item in day["schedule"] if item["type"] == "poi"]
    assert types[0] == "restaurant"
    assert meals[0]["name"] == "Tala Bay Cafe"
    assert "transfer" in types
    transfer = next(item for item in day["schedule"] if item["type"] == "transfer")
    assert transfer["time"] >= meals[0]["end_time"]
    assert len(meals) >= 3
    if pois:
        assert pois[0]["time"] >= transfer["end_time"]
        assert pois[0]["time"] >= "11:00"


def test_long_listings_still_pack_several_sights() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {**VALID_PACKAGE_REQUEST["trip"], "duration": "3", "preferredRegions": ["Aqaba"]},
        "preferences": {**VALID_PACKAGE_REQUEST["preferences"], "mustVisit": [], "placesToAvoid": ""},
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    intent = DayIntent(
        day=2,
        date="2026-08-22",
        region="Aqaba",
        region_key="aqaba",
        theme="Aqaba",
        sights=5,
        meals=3,
        overnight_key="aqaba",
        overnight_region="Aqaba",
    )
    shortlist = DayShortlist(
        day=2,
        region="Aqaba",
        region_key="aqaba",
        pois=[
            _card(f"p{i}", f"Site {i}", "poi", 180, "08:00", "18:00", region_key="aqaba", city="Aqaba")
            for i in range(1, 7)
        ],
        restaurants=[
            _card("r1", "Morning Cafe", "restaurant", 45, "07:00", "11:00", "Cafe", region_key="aqaba", city="Aqaba"),
            _card("r2", "Harbour Grill", "restaurant", 70, "12:00", "16:00", "Restaurant", region_key="aqaba", city="Aqaba"),
            _card("r3", "Evening Kitchen", "restaurant", 90, "17:00", "23:00", "Restaurant", region_key="aqaba", city="Aqaba"),
        ],
    )
    day = _build_day(
        intent,
        shortlist,
        include_hotel=False,
        check_in=False,
        heat=False,
        used_ids=set(),
        airport="AMM",
        profile=profile,
        stay_notes=[],
    )
    pois = [item for item in day["schedule"] if item["type"] == "poi"]
    meals = [item for item in day["schedule"] if item["type"] == "restaurant"]
    assert pois
    assert all(item.get("duration_minutes") == 180 for item in pois)
    assert len(meals) >= 3
    timed = [item for item in day["schedule"] if item.get("time") and item.get("end_time")]
    for left, right in zip(timed, timed[1:]):
        gap = _minutes_between(left["end_time"], right["time"])
        assert gap <= 90, (left["name"], right["name"], gap)

