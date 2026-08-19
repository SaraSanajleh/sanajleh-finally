"""End-to-end check of the retriever against a captured wizard case.

Expectations are derived from the request itself rather than hard-coded, so any case
in `case_capture/cases` can be checked: the areas the traveler named, the star rating
they asked for, and the number of days they booked.

    python scripts/verify_retriever_case.py [port] [case-dir-name]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.knowledge.planner_assist import build_planning_lock  # noqa: E402
from app.knowledge.wizard_payload import package_request_to_wizard_payload  # noqa: E402
from app.schemas.request.package_request import PackageRequest  # noqa: E402

CASES = ROOT / "case_capture" / "cases"
MAX_DAY_SPREAD_KM = 35.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = p2 - p1, radians(lon2 - lon1)
    h = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(h))


def norm(text: str) -> str:
    return re.sub(r"[^a-z ]", " ", str(text or "").lower()).strip()


def named_areas(request: PackageRequest) -> list[str]:
    labels = [r.value for r in request.trip.preferredRegions]
    labels += [m.value for m in request.preferences.mustVisit]
    return [norm(x) for x in labels if norm(x)]


def cluster_places(cluster: dict) -> set[str]:
    """Every geographic word a cluster's POIs carry (city, district, region)."""
    words: set[str] = set()
    for node in cluster.get("pois") or []:
        poi = node.get("poi") or {}
        for key in ("city", "district", "region", "name"):
            words |= set(norm(poi.get(key)).split())
    return {w for w in words if w}


def entity_ids(cluster: dict) -> tuple[set[str], set[str]]:
    pois, rests = set(), set()
    for node in cluster.get("pois") or []:
        poi = node.get("poi") or {}
        if poi.get("name"):
            pois.add(str(poi["name"]))
        for rest in node.get("restaurants") or []:
            if rest.get("name"):
                rests.add(str(rest["name"]))
    return pois, rests


def main() -> None:
    port = sys.argv[1] if len(sys.argv) > 1 else "8011"
    if len(sys.argv) > 2:
        case = CASES / sys.argv[2]
    else:
        case = max((p for p in CASES.iterdir() if p.is_dir()), key=lambda p: p.name)
    request = PackageRequest.model_validate(
        json.loads((case / "01_input.json").read_text(encoding="utf-8"))
    )

    payload = package_request_to_wizard_payload(request)
    resp = httpx.post(
        f"http://127.0.0.1:{port}/api/v1/knowledge/search", json=payload, timeout=300
    )
    resp.raise_for_status()
    data = resp.json()

    clusters = [c for c in (data.get("clusters") or []) if isinstance(c, dict)]
    areas = named_areas(request)
    stars = re.search(r"(\d)", str(request.accommodation.rating.value or ""))
    wanted = int(stars.group(1)) if stars else None

    print(f"case: {case.name}")
    print(f"named areas: {areas}  requested stars: {wanted}")
    print(f"duration_days={request.duration_days} clusters={len(clusters)}\n")

    for cluster in clusters:
        pois = [(n.get("poi") or {}) for n in (cluster.get("pois") or [])]
        hotels = cluster.get("hotels") or []
        print(f"cluster {cluster.get('cluster_id')} — {cluster.get('theme')}")
        print(f"  cities: {sorted({str(p.get('city')) for p in pois})}")
        print(f"  pois:   {[str(p.get('name')) for p in pois][:6]}")
        print(
            "  hotels: "
            + str([
                f"{h.get('name')} ({(h.get('facts') or {}).get('star_rating')}*)"
                for h in hotels
            ])
        )
        print()

    print("--- PLANNING LOCK the model will receive ---")
    print(build_planning_lock(data, request))
    print()

    failures: list[str] = []

    # 1) one day per booked day
    if len(clusters) != request.duration_days:
        failures.append(
            f"{len(clusters)} clusters for a {request.duration_days}-day trip"
        )

    # 2) each cluster must be drivable in one day. A governorate-level request legitimately
    #    spans villages, so coherence is a distance, not a single city name.
    for cluster in clusters:
        pts = [
            (poi.get("latitude"), poi.get("longitude"))
            for poi in ((n.get("poi") or {}) for n in (cluster.get("pois") or []))
            if poi.get("latitude") and poi.get("longitude")
        ]
        if len(pts) < 2:
            continue
        lat = sum(p[0] for p in pts) / len(pts)
        lon = sum(p[1] for p in pts) / len(pts)
        spread = max(haversine(lat, lon, p[0], p[1]) for p in pts)
        print(f"cluster {cluster.get('cluster_id')} spread: {spread:.1f} km")
        if spread > MAX_DAY_SPREAD_KM:
            failures.append(
                f"cluster {cluster.get('cluster_id')} spans {spread:.0f} km — not one day"
            )

    # 3) no cluster outside the areas the traveler named
    if areas:
        for cluster in clusters:
            words = cluster_places(cluster)
            if not any(any(tok in words for tok in area.split()) for area in areas):
                failures.append(
                    f"cluster {cluster.get('cluster_id')} sits outside the named areas "
                    f"({sorted(words)[:6]})"
                )

    # 4) clusters must not hand two days the same entity
    seen_pois: dict[str, int] = {}
    seen_rests: dict[str, int] = {}
    for cluster in clusters:
        cid = cluster.get("cluster_id")
        pois, rests = entity_ids(cluster)
        for name in pois:
            if name in seen_pois:
                failures.append(f"POI '{name}' in clusters {seen_pois[name]} and {cid}")
            seen_pois[name] = cid
        for name in rests:
            if name in seen_rests:
                failures.append(
                    f"restaurant '{name}' in clusters {seen_rests[name]} and {cid}"
                )
            seen_rests[name] = cid

    # 5) the requested rating leads wherever the area actually has it
    if wanted:
        for cluster in clusters:
            hotels = cluster.get("hotels") or []
            got = [(h.get("facts") or {}).get("star_rating") for h in hotels]
            available = [g for g in got if g and int(float(g)) == wanted]
            if available and not (got and got[0] and int(float(got[0])) == wanted):
                failures.append(
                    f"cluster {cluster.get('cluster_id')} leads with {got[0]}* while a "
                    f"{wanted}* hotel sits in the same list"
                )
            if not available:
                print(
                    f"note: cluster {cluster.get('cluster_id')} has no {wanted}* hotel "
                    f"(available: {got}) — the plan must state the rating it booked"
                )

    # 6) every named area is represented somewhere
    for area in areas:
        if not any(
            any(tok in cluster_places(c) for tok in area.split()) for c in clusters
        ):
            failures.append(f"named area '{area}' is missing from the evidence")

    if failures:
        print("FAILURES:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("OK: days match duration, single-city clusters inside the named areas, "
          "no entity shared between days, ratings honoured where they exist")


if __name__ == "__main__":
    main()
