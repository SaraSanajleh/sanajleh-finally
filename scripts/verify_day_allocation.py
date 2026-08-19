"""Verify day allocation + hotel tiering without loading the vector index.

Feeds `allocate_days` / `_region_attach` with metadata built straight from the
knowledge JSONs, so the planning logic can be checked in isolation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "retriever"))

from retrieval import (  # noqa: E402
    _region_attach,
    _region_match,
    _star_tier_fn,
    allocate_days,
)

KNOWLEDGE = ROOT / "data" / "customized_packages" / "knowledge"


def as_records(filename: str) -> list[dict]:
    """Mimic what search() returns: id + flat metadata + similarity."""
    rows = json.loads((KNOWLEDGE / filename).read_text(encoding="utf-8"))
    out = []
    for i, row in enumerate(rows):
        loc = row.get("location") or {}
        coords = loc.get("coordinates") or {}
        exp = row.get("experience") or {}
        star = exp.get("star_rating")
        out.append(
            {
                "id": row.get("id"),
                "similarity": 1.0 - (i / max(len(rows), 1)),
                "metadata": {
                    "name": (row.get("identity") or {}).get("name") or "",
                    "region": loc.get("region") or "",
                    "category": (row.get("identity") or {}).get("category") or "",
                    "lat": coords.get("latitude") or 0.0,
                    "lon": coords.get("longitude") or 0.0,
                    "star_rating": star if isinstance(star, (int, float)) else 0,
                    "location_json": json.dumps(loc, ensure_ascii=False),
                },
            }
        )
    return out


def main() -> None:
    pois = as_records("poi.json")
    hotels = as_records("hotel.json")

    prefs = {
        "preferredRegion": ["Wadi Rum", "Petra", "Aqaba"],
        "mustVisit": ["Wadi Rum", "Petra"],
        "arrivalAirport": "AMM",
    }
    days = allocate_days(prefs, 3, pois)

    print("=== day allocation for Wadi Rum + Petra + Aqaba, 3 days, arriving AMM ===")
    for i, day in enumerate(days, 1):
        members = [
            p["metadata"]["name"]
            for p in pois
            if any(_region_match(p["metadata"], t) for t in day["regions"])
        ]
        print(f"  Day {i}: area={day['regions']} forced={len(day['forced_ids'])} "
              f"matched_pois={len(members)}")
        print(f"          sample: {members[:4]}")
        assert members, f"day {i} matches no POIs: {day['regions']}"

    areas = [d["regions"][0] for d in days if d["regions"]]
    assert len(set(areas)) == 3, f"days collapsed: {areas}"
    for needle in ("petra", "rum", "aqaba"):
        assert any(needle in a for a in areas), f"{needle} day missing: {areas}"
    print("  OK: three separate destinations, one per day")

    print("\n=== hotel selection for a 5-star request in the Petra day ===")
    rank = {h["id"]: i for i, h in enumerate(hotels)}
    meta = {h["id"]: h["metadata"] for h in hotels}
    picks = _region_attach(
        rank,
        meta,
        {"ma'an"},
        4,
        locality_keys={"wadi musa"},
        tier_fn=_star_tier_fn(5),
    )
    for h in picks:
        m = h["metadata"]
        city = json.loads(m["location_json"]).get("city")
        print(f"  {m['name'][:40]:42s} star={m['star_rating']} city={city}")
    assert picks, "no hotels attached"
    assert all(int(float(h["metadata"]["star_rating"] or 0)) == 5 for h in picks), (
        "5-star request not honoured"
    )
    print("  OK: every pick is 5-star")

    print("\n=== same day, no rating requested (ranking order preserved) ===")
    plain = _region_attach(rank, meta, {"ma'an"}, 4, locality_keys={"wadi musa"})
    for h in plain:
        print(f"  {h['metadata']['name'][:40]:42s} star={h['metadata']['star_rating']}")

    print("\n=== fewer named areas than days: stay inside what was asked for ===")
    prefs = {
        "preferredRegion": ["Ajloun", "Jerash"],
        "mustVisit": ["Jerash"],
        "arrivalAirport": "AMM",
    }
    days = allocate_days(prefs, 3, pois)
    areas = [d["regions"][0] if d["regions"] else "" for d in days]
    for i, day in enumerate(days, 1):
        members = [
            p["metadata"]["name"]
            for p in pois
            if any(_region_match(p["metadata"], t) for t in day["regions"])
        ]
        print(f"  Day {i}: area={day['regions']} deepen={day.get('deepen', False)} "
              f"matched_pois={len(members)}")
    assert len(days) == 3, f"expected 3 days, got {len(days)}"
    assert all(
        any(named in a for named in ("ajloun", "jerash")) for a in areas
    ), f"a day landed outside the named areas: {areas}"
    assert set(areas) == {"ajloun", "jerash"}, f"a named area was dropped: {areas}"
    print("  OK: the spare day deepens a named area instead of importing one")

    print("\n=== a 4-star request where the area has none ===")
    for city, keys in (("Jerash", {"jerash"}), ("Ajloun", {"ajloun"})):
        picks = _region_attach(
            rank, meta, keys, 3, locality_keys=keys, tier_fn=_star_tier_fn(4)
        )
        shown = [
            f"{h['metadata']['name'][:34]}({h['metadata']['star_rating'] or '-'})"
            for h in picks
        ]
        print(f"  {city:8s}: {', '.join(shown) or '(none)'}")
    print("  (Ajloun has no 4-star card — the plan must say the rating it booked)")

    print("\n=== route direction follows the arrival airport ===")
    routes = {}
    for airport in ("AMM", "AQJ", "OTHER"):
        plan = allocate_days(
            {
                "preferredRegion": ["Wadi Rum", "Petra", "Aqaba"],
                "mustVisit": ["Wadi Rum", "Petra"],
                "arrivalAirport": airport,
            },
            3,
            pois,
        )
        routes[airport] = [d["regions"][0] for d in plan]
        print(f"  {airport:6s}: {' -> '.join(routes[airport])}")
    assert routes["AMM"][0] == "petra", "northern arrival should open in the north"
    assert routes["AQJ"][0] == "aqaba", "southern arrival should open in the south"
    assert routes["AMM"] == list(reversed(routes["AQJ"])), "route should just reverse"
    print("  OK: arrival airport decides the direction, same shortest path")


if __name__ == "__main__":
    main()
