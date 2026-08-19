# -*- coding: utf-8 -*-
"""
ReTour Retriever — G1 geography guard (landmark -> point seed).

Proves the QA-scandal fix WITHOUT building the vector index: we feed allocate_days
and select_anchors a `ranked` list built straight from the raw poi.json metadata
(the only fields these functions read are name/region/coords/category), then assert
the geographic behaviour:

  * a named PLACE (Petra) resolves to a POINT day centred on Petra — its anchors sit
    near Petra, NOT scattered across all of Ma'an governorate;
  * Petra + Wadi Rum (both in Ma'an, ~90 km apart) become TWO distinct day centres;
  * a sparse place (Dead Sea) still resolves honestly to its own point;
  * a real governorate (Amman) still behaves as a REGION day (no regression).

Run:  python test_geo_seeds.py        (from backend/retriever/)
"""
import os
import json

from geo import haversine
from retrieval import (allocate_days, select_anchors, _boost_prefs, _coord,
                       _place_blob, _ANCHOR_RADIUS_MAX_KM)

_HERE = os.path.dirname(os.path.abspath(__file__))
_KB = os.path.normpath(os.path.join(
    _HERE, "..", "..", "data", "customized_packages", "knowledge"))

PETRA = (30.3329, 35.4511)
WADI_RUM = (29.5459, 35.4382)
DEAD_SEA = (31.5741, 35.5976)


def build_ranked():
    """Fake best-first ranked list from raw poi.json (no embeddings needed)."""
    with open(os.path.join(_KB, "poi.json"), encoding="utf-8") as f:
        pois = json.load(f)
    ranked = []
    n = len(pois)
    for i, e in enumerate(pois):
        idn = e.get("identity", {}) or {}
        loc = e.get("location", {}) or {}
        coords = loc.get("coordinates", {}) or {}
        ranked.append({
            "id": e.get("id"),
            "metadata": {
                "name": idn.get("name", ""),
                "region": loc.get("region", ""),
                "category": idn.get("category", ""),
                "lat": coords.get("latitude"),
                "lon": coords.get("longitude"),
                "location_json": json.dumps(loc, ensure_ascii=False),
            },
            "similarity": 1.0 - (i / n),   # deterministic order
        })
    return ranked


def _has_place(anchors, token):
    return any(token in _place_blob(a["metadata"]) for a in anchors)


def _all_within(anchors, center, radius):
    for a in anchors:
        c = _coord(a["metadata"])
        assert c is not None, f"anchor {a['id']} has no coords"
        d = haversine(c[0], c[1], center[0], center[1])
        assert d <= radius + 0.5, f"anchor {a['id']} is {d:.1f} km > radius {radius:.1f}"


def main():
    ranked = build_ranked()
    bp = _boost_prefs({})
    print(f"loaded {len(ranked)} POIs")

    # --- 1) Petra alone -> ONE point day centred on Petra --------------------
    days = allocate_days({"preferredRegion": [], "mustVisit": ["Petra"]}, 1, ranked)
    assert len(days) == 1 and days[0]["kind"] == "point", days
    d = days[0]
    assert haversine(*d["center"], *PETRA) < 15, ("Petra centre off", d["center"])
    anchors, _ = select_anchors(d, ranked, set(), bp)
    assert anchors, "Petra day produced no anchors"
    _all_within(anchors, d["center"], d["radius_km"])
    assert _has_place(anchors, "petra"), "no Petra POI in the Petra day"
    assert not _has_place(anchors, "wadi rum"), "Wadi Rum leaked into the Petra day"
    print(f"  Petra: center={tuple(round(x,3) for x in d['center'])} "
          f"radius={d['radius_km']:.1f}km anchors={len(anchors)}  OK")

    # --- 2) Petra + Wadi Rum -> TWO distinct centres (same governorate!) ------
    days = allocate_days({"preferredRegion": [], "mustVisit": ["Petra", "Wadi Rum"]},
                         2, ranked)
    assert len(days) == 2, days
    assert all(x["kind"] == "point" for x in days), days
    by = {x["label"]: x for x in days}
    assert "petra" in by and "wadi rum" in by, by.keys()
    sep = haversine(*by["petra"]["center"], *by["wadi rum"]["center"])
    assert sep > 60, f"Petra & Wadi Rum centres only {sep:.1f} km apart (collapsed!)"
    used = set()
    pa, _ = select_anchors(by["petra"], ranked, used, bp)
    wa, _ = select_anchors(by["wadi rum"], ranked, used, bp)
    _all_within(pa, by["petra"]["center"], by["petra"]["radius_km"])
    _all_within(wa, by["wadi rum"]["center"], by["wadi rum"]["radius_km"])
    assert _has_place(pa, "petra") and _has_place(wa, "wadi rum")
    print(f"  Petra vs Wadi Rum: {sep:.1f} km apart, two separate days  OK")

    # --- 3) Dead Sea (sparse) -> honest point day ----------------------------
    days = allocate_days({"preferredRegion": [], "mustVisit": ["Dead Sea"]}, 1, ranked)
    assert len(days) == 1 and days[0]["kind"] == "point", days
    d = days[0]
    assert haversine(*d["center"], *DEAD_SEA) < 20, ("Dead Sea centre off", d["center"])
    anchors, _ = select_anchors(d, ranked, set(), bp)
    assert _has_place(anchors, "dead sea"), "no Dead Sea POI in the Dead Sea day"
    print(f"  Dead Sea: center={tuple(round(x,3) for x in d['center'])} "
          f"anchors={len(anchors)}  OK")

    # --- 4) Amman (a real governorate) -> REGION day (no regression) ---------
    days = allocate_days({"preferredRegion": [], "mustVisit": ["Amman"]}, 1, ranked)
    assert len(days) == 1 and days[0]["kind"] == "region", days
    anchors, _ = select_anchors(days[0], ranked, set(), bp)
    assert anchors, "Amman region day produced no anchors"
    assert all("amman" in (a["metadata"].get("region") or "").lower() for a in anchors)
    print(f"  Amman: region day, anchors={len(anchors)}  OK")

    # --- 5) G2 packing: two NEARBY governorates share one day ----------------
    days = allocate_days({"preferredRegion": ["Jerash", "Ajloun"], "mustVisit": []},
                         1, ranked)
    assert len(days) == 1, ("Jerash+Ajloun did not merge", days)
    assert {"jerash", "ajloun"} <= set(days[0]["regions"]), days[0]["regions"]
    print(f"  Jerash + Ajloun -> 1 shared day, regions={days[0]['regions']}  OK")

    # --- 6) G2 priority: mustVisit beats preferredRegion; overflow deferred ---
    deferred = []
    days = allocate_days({"preferredRegion": ["Amman"], "mustVisit": ["Petra"]},
                         1, ranked, deferred_out=deferred)
    assert len(days) == 1, days
    assert days[0]["kind"] == "point" and days[0]["label"] == "petra", days[0]
    assert deferred == ["amman"], deferred
    print(f"  Petra(must) kept over Amman(prefer); deferred={deferred}  OK")

    # --- 7) G2 honest deferral: two far mustVisits, one day -> defer one ------
    deferred = []
    days = allocate_days({"preferredRegion": [], "mustVisit": ["Petra", "Wadi Rum"]},
                         1, ranked, deferred_out=deferred)
    assert len(days) == 1, days
    kept = days[0]["label"]
    assert kept in ("petra", "wadi rum"), kept
    assert len(deferred) == 1 and deferred[0] != kept, (kept, deferred)
    print(f"  Petra+WadiRum in 1 day -> kept '{kept}', deferred {deferred}  OK")

    # --- 8) G3 route ordering: days visited as a nearest-neighbour path -------
    from retrieval import _order_route
    centres = [(31.0, 35.0), (33.0, 35.0), (31.5, 35.0), (32.0, 35.0)]
    assert _order_route(centres) == [0, 2, 3, 1], _order_route(centres)
    print("  route order (NN): [0,2,3,1]  OK")

    # --- 9) G3 corridor: among equal-interest candidates, the one that advances
    #        toward the NEXT day's anchor is preferred (soft, interest-first) ----
    from retrieval import select_discovery

    def _poi(pid, lat, lon, sim, cat="X", region="own"):
        return {"id": pid, "similarity": sim,
                "metadata": {"name": "", "region": region, "category": cat,
                             "lat": lat, "lon": lon, "location_json": "{}"}}

    anchor = _poi("A", 31.0, 35.0, 1.0, cat="X", region="own")
    toward = _poi("D_toward", 31.2, 35.0, 0.9, cat="Y", region="new")   # toward next
    away = _poi("D_away", 30.8, 35.0, 0.9, cat="Y", region="new")       # away from next
    day = {"kind": "region", "regions": ["own"], "hint_regions": [], "forced_ids": set()}
    disc = select_discovery(day, [anchor, toward, away], {"A"}, [anchor], [], bp,
                            set(), next_center=(31.5, 35.0))
    assert disc and disc[0]["id"] == "D_toward", [x["id"] for x in disc]
    print(f"  corridor: picked '{disc[0]['id']}' first (toward next day)  OK")

    # --- 10) G4 free_text place -> real anchor (not lost in the semantic soup) --
    days = allocate_days(
        {"preferredRegion": [], "mustVisit": [],
         "freeText": "we would love to wander around Jerash and its old ruins"},
        1, ranked)
    assert len(days) == 1, days
    assert "jerash" in days[0]["regions"] or days[0].get("label") == "jerash", days[0]
    assert days[0].get("priority") == "freetext", days[0]
    print("  free_text 'Jerash' -> anchor day (priority=freetext)  OK")

    print("\nG1 + G2 + G3 + G4 geography guard passed. OK")


if __name__ == "__main__":
    main()
