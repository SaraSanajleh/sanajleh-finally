from app.planning.profile import normalize_tourist_profile
from app.planning.route import plan_day_route
from app.schemas.request.package_request import PackageRequest
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST


def test_route_never_invents_unrequested_regions() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "preferredRegions": ["Ajloun", "Jerash"],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "mustVisit": ["Jerash"],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    route = plan_day_route(profile)
    keys = {stop.region_key for stop in route}
    assert keys <= {"amman", "ajloun", "jerash"}
    assert "balqa" not in keys
    assert "irbid" not in keys
    assert route[0].is_arrival_day
    assert route[0].region_key == "amman"
    assert route[0].overnight_key == "amman"
    assert any(stop.region_key == "jerash" for stop in route)
    assert len(route) == 4
    assert route[0].overnight_key == "amman"
    assert {stop.overnight_key for stop in route} <= {"amman", "ajloun", "jerash"}


def test_extra_days_go_to_explore_not_must_visit() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "4",
            "preferredRegions": ["Ajloun", "Jerash"],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "mustVisit": ["Jerash"],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    route = plan_day_route(profile)
    visit = [stop.region_key for stop in route if not stop.is_arrival_day]
    assert "jerash" in visit
    assert "ajloun" in visit
    assert visit.count("jerash") <= 2
    assert visit.count("ajloun") >= 1


def test_must_visit_on_both_halves_is_not_dropped() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "4",
            "preferredRegions": ["Jerash", "Petra"],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "mustVisit": ["Jerash", "Petra"],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    route = plan_day_route(profile)
    visit = {stop.region_key for stop in route if not stop.is_arrival_day}
    assert "jerash" in visit
    assert "petra" in visit


def test_named_explore_on_the_other_half_is_kept() -> None:
    """Destinations to explore stay on the route even if they sit across Jordan from the must-visit."""
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "arrivalAirport": "AQJ",
            "preferredRegions": ["Dead Sea"],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "mustVisit": ["Petra"],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    route = plan_day_route(profile)
    visit = [stop.region_key for stop in route if not stop.is_arrival_day]
    assert "petra" in visit
    assert "dead sea" in visit
    assert visit.count("petra") <= 2
    assert route[0].focus_half == "mixed"
    assert route[0].dropped_half == ""
    assert visit[0] == "petra"


def test_more_destinations_than_days_finishes() -> None:
    """3-day south trip with Petra + Wadi Rum + Aqaba used to hang the Brain."""
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "preferredRegions": ["Petra", "Wadi Rum", "Aqaba"],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "mustVisit": ["Petra"],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    route = plan_day_route(profile)
    assert len(route) == 4
    assert route[0].is_arrival_day
    visit_keys = [stop.region_key for stop in route if not stop.is_arrival_day]
    assert "petra" in visit_keys
    assert len(visit_keys) == 3


def test_short_south_trip_shares_one_hotel() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
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
    later = [stop for stop in route if not stop.is_arrival_day]
    assert len({stop.overnight_key for stop in later}) == 1


def test_enough_nights_allows_a_second_southern_hotel() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "5",
            "preferredRegions": ["Petra", "Wadi Rum"],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "mustVisit": ["Petra", "Wadi Rum"],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    route = plan_day_route(profile)
    later = [stop for stop in route if not stop.is_arrival_day]
    assert {stop.overnight_key for stop in later} >= {"petra", "wadi rum"}
    assert "petra" in {stop.region_key for stop in later}
    assert "wadi rum" in {stop.region_key for stop in later}


def test_desert_camp_prefers_wadi_rum_as_south_base() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "preferredRegions": ["Petra", "Wadi Rum"],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "mustVisit": ["Petra"],
            "placesToAvoid": "",
        },
        "accommodation": {"type": "desert_camp", "rating": "No Preference"},
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    route = plan_day_route(profile)
    later = [stop for stop in route if not stop.is_arrival_day]
    assert {stop.overnight_key for stop in later} == {"wadi rum"}


def test_aqaba_arrival_sleeps_in_aqaba_first() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "arrivalAirport": "AQJ",
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
    assert route[0].region_key == "aqaba"
    assert route[0].overnight_key == "aqaba"


def test_open_interests_do_not_dump_every_day_in_amman() -> None:
    """No wizard regions: follow interest clusters, keep one half of Jordan."""
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "preferredRegions": [],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "interests": ["nature", "adventure", "history"],
            "mustVisit": [],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    inferred = [
        ("Karak", "karak", False),
        ("Tafilah", "tafilah", False),
        ("Balqa", "balqa", False),
    ]
    route = plan_day_route(profile, inferred_dests=inferred)
    assert route[0].is_arrival_day
    assert route[0].region_key == "amman"
    visit = [stop.region_key for stop in route if not stop.is_arrival_day]
    assert visit
    assert "amman" not in visit
    assert "karak" in visit or "tafilah" in visit
    assert "balqa" not in visit
    from app.planning.geo import region_half

    assert {region_half(key) for key in visit} == {"south"}


def test_open_trip_without_evidence_stays_at_arrival() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "preferredRegions": [],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "mustVisit": [],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    route = plan_day_route(profile)
    assert [stop.region_key for stop in route] == ["amman", "amman", "amman", "amman"]


def test_wizard_regions_win_over_inferred_clusters() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "preferredRegions": ["Jerash", "Ajloun"],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "mustVisit": ["Jerash"],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    route = plan_day_route(
        profile,
        inferred_dests=[("Karak", "karak", False), ("Tafilah", "tafilah", False)],
    )
    keys = {stop.region_key for stop in route}
    assert "karak" not in keys
    assert "jerash" in keys or "ajloun" in keys


def test_destinations_from_clusters_uses_poi_regions() -> None:
    from app.planning.route import destinations_from_clusters

    dests = destinations_from_clusters(
        {
            "clusters": [
                {"pois": [{"poi": {"region": "Karak Governorate"}}]},
                {"theme": "Tafilah Governorate · nature"},
                {"pois": [{"poi": {"region": "Balqa Governorate"}}]},
            ]
        }
    )
    assert [key for _, key, _ in dests] == ["balqa", "karak", "tafilah"]


def test_open_trip_follows_retriever_clusters_not_catalog_cities() -> None:
    """No named dests: the retriever clusters are the trip, not catalog Amman/Jerash."""
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "5",
            "preferredRegions": [],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "interests": ["culture"],
            "mustVisit": [],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    from app.planning.route import apply_open_trip_evidence

    profile, dests = apply_open_trip_evidence(
        profile,
        {
            "clusters": [
                {"theme": "Tafilah Governorate · culture"},
                {"theme": "Karak Governorate · culture"},
                {"theme": "Madaba Governorate · culture"},
                {"theme": "Balqa Governorate · culture"},
                {"theme": "Aqaba Governorate · culture"},
            ]
        },
    )
    keys = {key for _, key, _ in dests}
    assert "karak" in keys
    assert "tafilah" in keys
    assert "jerash" not in keys
    route = plan_day_route(profile, inferred_dests=dests)
    visit = [stop.region_key for stop in route if not stop.is_arrival_day]
    assert "jerash" not in visit
    assert {"karak", "tafilah"} & set(visit)
    assert "balqa" not in visit


def test_open_trip_without_clusters_uses_catalog_interests() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "preferredRegions": [],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "interests": ["religious_sites", "museums"],
            "mustVisit": [],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    from app.planning.route import apply_open_trip_evidence

    profile, dests = apply_open_trip_evidence(profile, {"clusters": []})
    keys = {key for _, key, _ in dests}
    assert "karak" not in keys
    assert "tafilah" not in keys
    assert keys & {"amman", "madaba", "jerash"}
    route = plan_day_route(profile, inferred_dests=dests)
    visit = {stop.region_key for stop in route if not stop.is_arrival_day}
    assert "karak" not in visit
    assert visit & {"amman", "madaba", "jerash"}


def test_five_explore_days_still_keep_the_named_south_dest() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "5",
            "preferredRegions": ["Jerash", "Petra"],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "mustVisit": ["Jerash"],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    route = plan_day_route(profile)
    visit = {stop.region_key for stop in route if not stop.is_arrival_day}
    assert "jerash" in visit
    assert "petra" in visit
    assert route[0].focus_half == "mixed"
    assert route[0].dropped_half == ""


def test_six_explore_days_may_mix_north_and_south() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "6",
            "preferredRegions": ["Jerash", "Petra"],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "mustVisit": [],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    route = plan_day_route(profile)
    visit = {stop.region_key for stop in route if not stop.is_arrival_day}
    assert "jerash" in visit
    assert "petra" in visit
    assert route[0].focus_half == "mixed"


def test_aqj_north_trip_sleeps_in_aqaba_then_relocates() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "arrivalAirport": "AQJ",
            "preferredRegions": ["Jerash", "Ajloun"],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "mustVisit": ["Jerash"],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    route = plan_day_route(profile)
    assert route[0].is_arrival_day
    assert route[0].region_key == "aqaba"
    assert route[0].overnight_key == "aqaba"
    visit = [stop for stop in route if not stop.is_arrival_day]
    assert visit
    assert all(stop.region_key != "aqaba" for stop in visit)
    assert any(stop.region_key == "jerash" for stop in visit)
    assert visit[0].overnight_key != "aqaba"


def _explored_keys(route) -> set[str]:
    keys: set[str] = set()
    for stop in route:
        if stop.is_arrival_day:
            continue
        keys.add(stop.region_key)
        if stop.paired_key:
            keys.add(stop.paired_key)
    return keys


def test_single_must_visit_spreads_extra_days_nearby() -> None:
    """5 exploring days and only Jerash as must-visit should not be 5 days in Jerash."""
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "5",
            "preferredRegions": [],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "mustVisit": ["Jerash"],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    route = plan_day_route(profile)
    visit = [stop.region_key for stop in route if not stop.is_arrival_day]
    nearby = {"ajloun", "amman", "madaba", "irbid", "dead sea"}
    assert "jerash" in visit
    assert visit.count("jerash") < 5
    assert _explored_keys(route) & nearby
    from app.planning.geo import region_half

    assert {region_half(key) for key in visit} == {"north_center"}


def test_must_visit_without_explore_dests_keeps_two_days_then_goes_nearby() -> None:
    """A must-visit can fill two exploring days. A third day goes somewhere close, not more of the same."""
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "preferredRegions": [],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "interests": ["nature", "food", "photography"],
            "mustVisit": ["Dead Sea"],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    route = plan_day_route(profile)
    visit = [stop.region_key for stop in route if not stop.is_arrival_day]
    nearby = {"madaba", "amman", "jerash", "ajloun", "salt", "irbid"}
    assert visit.count("dead sea") == 2
    assert _explored_keys(route) & nearby
    assert len(visit) == 3


def test_must_gets_two_days_and_explore_still_appears() -> None:
    """Must-visit can take two days. The named explore dest still gets a day."""
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "preferredRegions": ["Madaba"],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "mustVisit": ["Dead Sea"],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    route = plan_day_route(profile)
    visit = [stop.region_key for stop in route if not stop.is_arrival_day]
    assert "dead sea" in visit
    assert "madaba" in visit
    assert visit.count("dead sea") == 2
    assert visit.count("madaba") >= 1


def test_more_explore_regions_than_days_drops_the_farthest() -> None:
    """3 exploring days and 4 named dests: keep a tight loop, drop the outlier."""
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "preferredRegions": ["Jerash", "Ajloun", "Madaba", "Irbid"],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "mustVisit": [],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    route = plan_day_route(profile)
    visit = _explored_keys(route)
    assert len(visit) <= 3
    assert "jerash" in visit or "ajloun" in visit
    assert "madaba" not in visit


def test_two_close_explore_regions_can_share_a_day() -> None:
    """When days are tight, Madaba and the Dead Sea may share a day instead of dropping one."""
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "2",
            "arrivalAirport": "AQJ",
            "preferredRegions": ["Madaba", "Dead Sea", "Amman"],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "mustVisit": [],
            "placesToAvoid": "",
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    route = plan_day_route(profile)
    visit = _explored_keys(route)
    explore_days = [stop for stop in route if not stop.is_arrival_day]
    assert len(explore_days) == 2
    assert "madaba" in visit
    assert "dead sea" in visit
    assert "amman" in visit
    assert any(stop.paired_key for stop in explore_days)


def test_named_explore_dest_does_not_fill_every_day() -> None:
    """A single destination-to-explore still gets at most two days; leftover goes nearby."""
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
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    route = plan_day_route(profile)
    visit = [stop.region_key for stop in route if not stop.is_arrival_day]
    nearby = {"madaba", "amman", "jerash", "ajloun", "salt", "irbid"}
    assert visit.count("dead sea") == 2
    assert _explored_keys(route) & nearby
    assert len(visit) == 3
