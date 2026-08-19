# -*- coding: utf-8 -*-
"""
ReTour Retriever — region lock.

When the wizard names destinations, the retriever must not leak a neighbouring
governorate just because it is 15–25 km away. Al-Husun (Irbid) next to Jerash
is the canonical case; the rule is general.

Run:  python test_region_lock.py        (from backend/retriever/)
      pytest test_region_lock.py
"""
from normalize import region_key
from retrieval import (
    allocate_days, select_discovery, select_anchors, _attach, _boost_prefs,
    _in_day_regions, _region_key_of,
)


def _poi(pid, name, region, lat, lon, sim=0.9, cat="Site"):
    return {
        "id": pid,
        "similarity": sim,
        "metadata": {
            "name": name,
            "region": region,
            "region_key": region_key(region),
            "category": cat,
            "lat": lat,
            "lon": lon,
        },
    }


# Jerash city ~32.28, 35.89; Al-Husun ~32.49, 35.86 (~23 km)
JERASH = _poi("j1", "Jerash Archaeological City", "Jerash Governorate",
              32.2800, 35.8900, 1.00)
JERASH_B = _poi("j2", "Jerash Museum", "Jerash Governorate",
                32.2760, 35.8910, 0.93, cat="Museum")
AJLOUN = _poi("a1", "Ajloun Castle", "Ajloun Governorate",
              32.3320, 35.7520, 0.95)
HUSUN = _poi("i1", "Al-Husun Traditional Pottery Studio", "Irbid Governorate",
             32.4889, 35.8594, 0.94, cat="Shopping")
IRBID_SOUQ = _poi("i2", "Al-Husun Old Souq", "Irbid Governorate",
                  32.4900, 35.8500, 0.90, cat="Shopping")
IRBID_MILL = _poi("i3", "Tawaheen Al-Hawa Irbid", "Irbid Governorate",
                  32.5550, 35.8500, 0.88)

RANKED = [JERASH, AJLOUN, HUSUN, JERASH_B, IRBID_SOUQ, IRBID_MILL]
PREFS = {"preferredRegion": ["Jerash", "Ajloun"], "mustVisit": []}


def test_allocate_days_does_not_invent_irbid():
    days = allocate_days(PREFS, 3, RANKED)
    assert len(days) == 3
    blob = " ".join(" ".join(d["regions"]) for d in days).lower()
    assert "irbid" not in blob
    keys = {region_key(t) for d in days for t in d["regions"]}
    assert keys <= {"jerash", "ajloun"}
    assert {"jerash", "ajloun"} <= keys


def test_allocate_must_only_uses_a_nearby_day_instead_of_a_third_copy():
    days = allocate_days({"preferredRegion": [], "mustVisit": ["Jerash"]}, 3, RANKED)
    assert len(days) == 3
    jerash_n = sum(1 for day in days if any("jerash" in (reg or "") for reg in day["regions"]))
    assert jerash_n <= 2
    blob = " ".join(" ".join(day["regions"]) for day in days).lower()
    assert "ajloun" in blob


def test_allocate_dead_sea_does_not_clone_madaba():
    """Dead Sea is not a governorate in the catalog. Do not rewrite it to Madaba
    and then copy that Madaba cluster three times."""
    panorama = _poi(
        "ds1", "Dead Sea Panorama Complex", "Madaba Governorate",
        31.5900, 35.4700, 1.00,
    )
    mosaic = _poi(
        "m1", "St George Church", "Madaba Governorate",
        31.7160, 35.7940, 0.92, cat="Church",
    )
    ranked = [panorama, mosaic, JERASH, AJLOUN]
    days = allocate_days({"preferredRegion": [], "mustVisit": ["Dead Sea"]}, 3, ranked)
    assert len(days) == 3
    blob = " ".join(" ".join(day["regions"]) for day in days).lower()
    keys = [region_key(token) for day in days for token in day["regions"]]
    assert keys.count("dead sea") <= 2
    assert keys.count("dead sea") >= 1
    assert keys.count("madaba") < 3
    assert "dead sea" in blob
    assert not all("madaba" in " ".join(day["regions"]) for day in days)


def test_discovery_rejects_nearby_foreign_governorate():
    bp = _boost_prefs({})
    day = {"regions": ["jerash"], "hint_regions": [], "forced_ids": set()}
    used = {JERASH["id"]}
    disc = select_discovery(day, RANKED, used, [JERASH], [JERASH_B], bp, {"ajloun"})
    names = [p["metadata"]["name"].lower() for p in disc]
    keys = {_region_key_of(p["metadata"]) for p in disc}
    assert all("husun" not in n and "irbid" not in n for n in names), names
    assert "irbid" not in keys
    assert all(_in_day_regions(p["metadata"], day) for p in disc)


def test_anchors_stay_inside_requested_region():
    bp = _boost_prefs({})
    day = {"regions": ["jerash"], "hint_regions": [], "forced_ids": set()}
    anchors, surplus = select_anchors(day, RANKED, set(), bp)
    for p in anchors + surplus:
        assert _region_key_of(p["metadata"]) == "jerash", p["metadata"]["name"]


def test_restaurants_cannot_hitchhike_from_irbid():
    jerash_rest = {
        "id": "r_jerash",
        "metadata": {"name": "Jerash Grill", "region": "Jerash Governorate",
                     "region_key": "jerash"},
    }
    irbid_rest = {
        "id": "r_irbid",
        "metadata": {"name": "Buffalo Wings & Rings Irbid",
                     "region": "Irbid Governorate", "region_key": "irbid"},
    }
    neighbors = [
        {"id": "r_irbid", "distance_meters": 800},
        {"id": "r_jerash", "distance_meters": 1200},
    ]
    rank_pos = {"r_irbid": 0, "r_jerash": 1}
    meta_map = {jerash_rest["id"]: jerash_rest["metadata"],
                irbid_rest["id"]: irbid_rest["metadata"]}
    attached = _attach(neighbors, rank_pos, meta_map, 6,
                       allowed_keys={"jerash"})
    assert [c["id"] for c in attached] == ["r_jerash"]


def main():
    test_allocate_days_does_not_invent_irbid()
    print("  allocate_days: 3-day Jerash+Ajloun never infers Irbid  OK")
    test_allocate_must_only_uses_a_nearby_day_instead_of_a_third_copy()
    print("  allocate_days: must-only leftover infers a nearby day  OK")
    test_allocate_dead_sea_does_not_clone_madaba()
    print("  allocate_days: Dead Sea stays Dead Sea, not 3x Madaba  OK")
    test_discovery_rejects_nearby_foreign_governorate()
    print("  discovery: Al-Husun (Irbid, ~23km) stays out of Jerash day  OK")
    test_anchors_stay_inside_requested_region()
    print("  anchors: Jerash day only Jerash POIs  OK")
    test_restaurants_cannot_hitchhike_from_irbid()
    print("  restaurants: Irbid neighbour dropped on Jerash POI  OK")
    print("\nregion lock passed. OK")


if __name__ == "__main__":
    main()
