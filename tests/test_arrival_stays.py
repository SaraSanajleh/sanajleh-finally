from datetime import timedelta

from app.planning.arrival import arrival_beats, plan_arrival
from app.planning.profile import normalize_tourist_profile
from app.planning.route import plan_day_route
from app.planning.stays import pick_stay_hotel
from app.retrieval.knowledge import KnowledgeCard
from app.schemas.request.package_request import PackageRequest
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST


def test_overnight_landing_sleeps_then_still_gets_a_day() -> None:
    plan = plan_arrival("03:02", "Balanced", "AMM")
    assert plan.window == "overnight"
    assert plan.meal_first is False
    assert plan.allow_activities is True
    assert plan.activity_count >= 1
    beats = arrival_beats(plan)
    kinds = [beat.kind for beat in beats]
    assert kinds[0] == "hotel"
    assert kinds.count("poi") >= 2
    assert kinds.count("meal") >= 2
    hotel = beats[0]
    wake = hotel.start + timedelta(minutes=hotel.minutes)
    assert wake.hour >= 10
    breakfast = next(beat for beat in beats if beat.kind == "meal")
    assert breakfast.start.hour >= 7
    last_poi = [beat for beat in beats if beat.kind == "poi"][-1]
    assert last_poi.start.hour >= 12


def test_any_pre_dawn_landing_fills_the_remaining_day() -> None:
    for stamp in ("01:15", "03:02", "05:40"):
        plan = plan_arrival(stamp, "Balanced", "AMM")
        kinds = [beat.kind for beat in arrival_beats(plan)]
        assert kinds[0] == "hotel"
        assert kinds.count("poi") >= 2
        assert "meal" in kinds
    plan = plan_arrival("08:00", "Balanced", "AMM")
    assert plan.window == "daytime"
    assert plan.meal_first is True
    assert plan.allow_activities is True
    kinds = [beat.kind for beat in arrival_beats(plan)]
    assert kinds[0] == "meal"
    assert "hotel" in kinds
    assert kinds.count("poi") >= 2


def test_evening_arrival_is_dinner_and_sleep() -> None:
    plan = plan_arrival("18:30", "Balanced", "AMM")
    assert plan.window == "twilight"
    kinds = [beat.kind for beat in arrival_beats(plan)]
    assert "poi" not in kinds


def test_late_arrival_is_meal_and_rest_only() -> None:
    plan = plan_arrival("21:30", "Balanced")
    assert plan.window == "night"
    assert plan.allow_activities is False
    kinds = [beat.kind for beat in arrival_beats(plan)]
    assert "poi" not in kinds


def test_mid_morning_arrival_builds_a_mini_itinerary() -> None:
    plan = plan_arrival("10:00", "Balanced", "AMM")
    assert plan.window == "daytime"
    assert plan.activity_count >= 2
    kinds = [beat.kind for beat in arrival_beats(plan)]
    assert kinds.count("poi") >= 2
    assert kinds[0] == "meal"
    assert "hotel" in kinds


def test_late_afternoon_arrival_does_not_force_sightseeing() -> None:
    plan = plan_arrival("14:00", "Balanced", "AMM")
    assert plan.window == "daytime"
    remaining_after_rest = plan.activity_count
    if remaining_after_rest == 0:
        kinds = [beat.kind for beat in arrival_beats(plan)]
        assert "poi" not in kinds


def test_amman_south_trip_keeps_one_southern_hotel() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "4",
            "arrivalAirport": "AMM",
            "preferredRegions": ["Petra", "Wadi Rum"],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "mustVisit": ["Petra"],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    route = plan_day_route(profile)
    assert route[0].overnight_key == "amman"
    later = [stop for stop in route if not stop.is_arrival_day]
    assert later
    visit = [stop.region_key for stop in later]
    assert "petra" in visit
    assert "wadi rum" in visit
    assert visit.count("wadi rum") >= visit.count("petra")
    assert len({stop.overnight_key for stop in later}) == 1


def test_hotel_pick_prefers_requested_stars_over_closer_lower_tier() -> None:
    five = KnowledgeCard(
        item_id="h_five",
        entity_type="hotel",
        name="Five Star House",
        region_key="amman",
        city="Amman",
        latitude=31.95,
        longitude=35.93,
        relevance=0.4,
        facts={"star_rating": 5, "night_price": 200},
    )
    three = KnowledgeCard(
        item_id="h_three",
        entity_type="hotel",
        name="Three Star Airport",
        region_key="amman",
        city="Amman",
        latitude=31.73,
        longitude=35.99,
        relevance=0.9,
        facts={"star_rating": 3, "night_price": 40},
    )
    profile = normalize_tourist_profile(
        PackageRequest.model_validate(
            {
                **VALID_PACKAGE_REQUEST,
                "accommodation": {"type": "hotel", "rating": "5 star"},
            }
        )
    )
    picked = pick_stay_hotel(
        [three, five],
        "amman",
        near_lat=31.72255,
        near_lon=35.99321,
        profile=profile,
    )
    assert picked is not None
    assert picked.item_id == "h_five"


def test_hotel_pick_prefers_closer_gps() -> None:
    near = KnowledgeCard(
        item_id="h_near",
        entity_type="hotel",
        name="Airport Hotel",
        region_key="amman",
        city="Amman",
        latitude=31.73,
        longitude=35.99,
        relevance=0.4,
    )
    far = KnowledgeCard(
        item_id="h_far",
        entity_type="hotel",
        name="City Hotel",
        region_key="amman",
        city="Amman",
        latitude=31.95,
        longitude=35.93,
        relevance=0.9,
    )
    picked = pick_stay_hotel([far, near], "amman", near_lat=31.72255, near_lon=35.99321)
    assert picked is not None
    assert picked.item_id == "h_near"
