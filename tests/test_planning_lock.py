"""The planning lock must hand each day its own evidence and tell the truth about it."""

from __future__ import annotations

from app.knowledge.planner_assist import build_planning_lock
from app.schemas.request.package_request import PackageRequest
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST


def _request(regions: list[str], must: list[str], rating: str = "4 star",
             days: int = 3) -> PackageRequest:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "preferredRegions": regions,
            "duration": str(days),
        },
        "preferences": {**VALID_PACKAGE_REQUEST["preferences"], "mustVisit": must},
        "accommodation": {**VALID_PACKAGE_REQUEST["accommodation"], "rating": rating},
    }
    return PackageRequest.model_validate(payload)


def _cluster(cid: int, theme: str, city: str, pois: list[str],
             hotels: list[tuple[str, int | None]],
             points: list[tuple[float, float]] | None = None) -> dict:
    return {
        "cluster_id": cid,
        "theme": theme,
        "pois": [
            {"poi": {"name": name, "city": city, "region": theme,
                     "facts": {"entry_fee": 10 + i},
                     **(
                         {"latitude": points[i][0], "longitude": points[i][1]}
                         if points and i < len(points)
                         else {}
                     )}}
            for i, name in enumerate(pois)
        ],
        "hotels": [
            {"name": name, "facts": {"star_rating": stars} if stars else {}}
            for name, stars in hotels
        ],
    }


def _payload(clusters: list[dict], days: int = 3) -> dict:
    return {"duration_days": days, "clusters": clusters}


JERASH = _cluster(0, "Jerash Governorate", "Jerash",
                  ["Hippodrome of Jerash", "Dibbeen Forest Reserve"],
                  [("Celestia Boutique Inn", 4), ("Jerash Hotel", 2)])
AJLOUN_1 = _cluster(1, "Ajloun Governorate", "Ajloun",
                    ["Ajloun Forest Reserve", "Wadi Rayyan"],
                    [("Al-Jabal Castle Hotel", 2)])
AJLOUN_2 = _cluster(2, "Ajloun Governorate", "Ajloun",
                    ["Wadi Orjan", "Ishtafina Park"],
                    [("Al-Jabal Castle Hotel", 2)])


def test_every_cluster_gets_its_own_day() -> None:
    """Two clusters in one area are two days out, not one day used twice."""
    lock = build_planning_lock(
        _payload([JERASH, AJLOUN_1, AJLOUN_2]), _request(["Ajloun", "Jerash"], ["Jerash"])
    )
    route = next(line for line in lock.splitlines() if "Day→cluster route" in line)

    assert "D1:C0" in route and "D2:C1" in route and "D3:C2" in route
    assert "part 1" in route and "part 2" in route


def test_a_second_day_in_one_area_is_labelled_as_such() -> None:
    lock = build_planning_lock(
        _payload([AJLOUN_1, AJLOUN_2], days=2), _request(["Ajloun"], [], days=2)
    )
    route = next(line for line in lock.splitlines() if "Day→cluster route" in line)

    assert route.count("Ajloun") == 2


def test_lodging_states_the_rating_it_actually_booked() -> None:
    """A thin area cannot honour a 4-star request; the lock must say so, per night."""
    lock = build_planning_lock(
        _payload([JERASH, AJLOUN_1, AJLOUN_2]), _request(["Ajloun", "Jerash"], ["Jerash"])
    )
    lodging = next(line for line in lock.splitlines() if "Per-night base" in line)

    assert "N1(C0): Celestia Boutique Inn [4-star]" in lodging
    assert "N2(C1): Al-Jabal Castle Hotel [2-star]" in lodging
    assert "4-star unavailable in this area" in lodging
    assert "N3" not in lodging          # three days means two nights


def test_named_areas_are_stated_as_the_whole_trip() -> None:
    lock = build_planning_lock(
        _payload([JERASH, AJLOUN_1, AJLOUN_2]), _request(["Ajloun", "Jerash"], ["Jerash"])
    )

    assert "Plan ONLY in these areas" in lock
    assert "No entity twice in the whole trip" in lock


def test_the_money_line_carries_the_party_and_the_daily_room() -> None:
    request = _request(["Jerash"], [])
    lock = build_planning_lock(_payload([JERASH]), request)
    money = next(line for line in lock.splitlines() if line.startswith("- Money:"))
    heads = (
        request.travelers.adults
        + request.travelers.children
        + request.travelers.seniors
    )

    assert f"{heads} traveller" in money
    assert "JOD/day" in money


def test_pois_inside_one_site_are_reported_as_one_visit() -> None:
    """Monuments a few hundred metres apart are one ticket, not two half-hour stops."""
    ruins = _cluster(
        0, "Jerash Governorate", "Jerash",
        ["Hippodrome of Jerash", "North Theater of Jerash", "Suf Village Heritage Center"],
        [("Celestia Boutique Inn", 4)],
        points=[(32.27415, 35.88941), (32.27600, 35.89100), (32.33000, 35.83000)],
    )
    lock = build_planning_lock(_payload([ruins], days=2), _request(["Jerash"], [], days=2))
    line = next(li for li in lock.splitlines() if "One visit, one fee" in li)

    assert "Hippodrome of Jerash + North Theater of Jerash" in line
    assert "Suf Village" not in line


def test_a_scattered_cluster_reports_no_shared_site() -> None:
    spread = _cluster(
        0, "Ajloun Governorate", "Ajloun", ["Wadi Orjan", "Ishtafina Park"],
        [("Ajloun Hotel", 2)],
        points=[(32.33000, 35.75000), (32.40000, 35.68000)],
    )
    lock = build_planning_lock(_payload([spread], days=2), _request(["Ajloun"], [], days=2))

    assert "(no such groups here)" in lock


def test_the_day_shape_and_alternative_rules_are_stated() -> None:
    lock = build_planning_lock(
        _payload([JERASH, AJLOUN_1, AJLOUN_2]), _request(["Ajloun", "Jerash"], ["Jerash"])
    )

    assert "3 sights + lunch + dinner" in lock
    assert "UNUSED entities" in lock
    assert "Entry fees are the last thing to cut" in lock


def test_lodging_arithmetic_is_spelled_out_for_the_party() -> None:
    request = _request(["Jerash"], [])
    lock = build_planning_lock(_payload([JERASH]), request)
    money = next(line for line in lock.splitlines() if line.startswith("- Money:"))
    heads = (
        request.travelers.adults
        + request.travelers.children
        + request.travelers.seniors
    )

    assert f"x ~{max((heads + 1) // 2, 1)} room(s)" in money
    assert "night(s)" in money


def test_no_hotel_card_is_admitted_rather_than_invented() -> None:
    bare = _cluster(0, "Jerash Governorate", "Jerash", ["Hippodrome of Jerash"], [])
    lock = build_planning_lock(_payload([bare], days=2), _request(["Jerash"], [], days=2))

    assert "no hotel card" in lock
