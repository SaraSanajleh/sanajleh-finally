"""Deterministic planning assist — prune evidence + short PLANNING LOCK for the LLM."""

from __future__ import annotations

import re
from typing import Any

from app.schemas.request.package_request import PackageRequest

# Classic tourist corridor (arrival AMM → south → optional beach/desert).
_CORRIDOR = [
    "Amman",
    "Jerash",
    "Ajloun",
    "Irbid",
    "Madaba",
    "Dead Sea",
    "Petra",
    "Wadi Rum",
    "Aqaba",
]

_REGION_ALIASES: dict[str, tuple[str, ...]] = {
    "amman": ("amman",),
    "jerash": ("jerash", "jarash"),
    "ajloun": ("ajloun", "ajlun"),
    "irbid": ("irbid",),
    "madaba": ("madaba",),
    "dead sea": ("dead sea", "deadsea", "suweimeh", "balqa", "al balqa"),
    "petra": ("petra", "wadi musa", "ma'an", "maan", "ma an"),
    "wadi rum": ("wadi rum", "rum", "protected area"),
    "aqaba": ("aqaba", "aqaba governorate"),
}


def _norm(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _haystack(cluster: dict[str, Any]) -> str:
    parts = [
        cluster.get("theme"),
        cluster.get("summary"),
        str(cluster.get("cluster_id")),
    ]
    for node in cluster.get("pois") or []:
        if not isinstance(node, dict):
            continue
        poi = node.get("poi") or {}
        parts.extend(
            [
                poi.get("name"),
                poi.get("region"),
                poi.get("city"),
                poi.get("district"),
                " ".join(str(w) for w in (poi.get("why_retrieved") or [])),
            ]
        )
        for rest in node.get("restaurants") or []:
            if isinstance(rest, dict):
                parts.append(rest.get("name"))
    for hotel in cluster.get("hotels") or []:
        if isinstance(hotel, dict):
            parts.extend([hotel.get("name"), hotel.get("region"), hotel.get("city")])
    return _norm(" ".join(str(p) for p in parts if p))


def _matches_label(label: str, haystack: str) -> bool:
    key = _norm(label)
    if not key:
        return False
    if key in haystack:
        return True
    for alias in _REGION_ALIASES.get(key, ()):
        if alias in haystack:
            return True
    # Landmark fragments (e.g. "Petra Archaeological Park")
    token = key.split()[0]
    return len(token) >= 4 and token in haystack


def _corridor_index(label: str) -> int:
    key = _norm(label)
    for i, region in enumerate(_CORRIDOR):
        if _norm(region) == key or key in _REGION_ALIASES.get(_norm(region), ()):
            return i
    for i, region in enumerate(_CORRIDOR):
        if _matches_label(region, key):
            return i
    return 50


def _role_rank(card: dict[str, Any]) -> int:
    role = _norm(card.get("role"))
    if role == "anchor":
        return 0
    if role == "discovery":
        return 1
    return 2


def _score_cluster(cluster: dict[str, Any], request: PackageRequest) -> int:
    hay = _haystack(cluster)
    score = 0
    for region in request.trip.preferredRegions:
        if _matches_label(region.value, hay):
            score += 40
    for place in request.preferences.mustVisit:
        if _matches_label(place.value, hay):
            score += 60
    # Prefer clusters that already contain anchors.
    for node in cluster.get("pois") or []:
        if isinstance(node, dict) and _role_rank(node.get("poi") or {}) == 0:
            score += 5
    return score


def prune_evidence_payload(
    payload: dict[str, Any],
    request: PackageRequest,
    *,
    max_pois_per_cluster: int = 4,
    max_restaurants_per_poi: int = 2,
    max_hotels_per_cluster: int = 2,
    max_events_per_cluster: int = 1,
) -> dict[str, Any]:
    """Keep preference-aligned clusters and cap cards — faster + sharper planning."""
    clusters = [c for c in (payload.get("clusters") or []) if isinstance(c, dict)]
    if not clusters:
        return payload

    scored = sorted(
        clusters,
        key=lambda c: (-_score_cluster(c, request), c.get("cluster_id", 0)),
    )
    duration = int(payload.get("duration_days") or request.duration_days or len(scored))
    # Keep enough geographic variety for the route, not the whole dump.
    keep_n = max(duration, len(request.trip.preferredRegions) or 0, 1)
    keep_n = min(len(scored), keep_n + 1)

    preferred_hits = [
        c for c in scored if _score_cluster(c, request) > 0
    ]
    selected = preferred_hits[:keep_n] if preferred_hits else scored[:keep_n]
    # Preserve corridor geography for the kept set.
    selected.sort(
        key=lambda c: (
            min(
                (
                    _corridor_index(r.value)
                    for r in request.trip.preferredRegions
                    if _matches_label(r.value, _haystack(c))
                ),
                default=50,
            ),
            c.get("cluster_id", 0),
        )
    )

    pruned_clusters: list[dict[str, Any]] = []
    for cluster in selected:
        nodes = [n for n in (cluster.get("pois") or []) if isinstance(n, dict)]
        nodes.sort(key=lambda n: (_role_rank(n.get("poi") or {}), n.get("poi", {}).get("name") or ""))
        slim_nodes = []
        for node in nodes[:max_pois_per_cluster]:
            rests = [r for r in (node.get("restaurants") or []) if isinstance(r, dict)]
            slim_nodes.append(
                {
                    **node,
                    "restaurants": rests[:max_restaurants_per_poi],
                    "distances_to_others": (node.get("distances_to_others") or [])[:5],
                }
            )
        hotels = [h for h in (cluster.get("hotels") or []) if isinstance(h, dict)]
        hotels.sort(
            key=lambda h: (
                0 if _hotel_pref_score(h, request) > 0 else 1,
                -_hotel_pref_score(h, request),
                h.get("name") or "",
            )
        )
        events = [e for e in (cluster.get("events") or []) if isinstance(e, dict)]
        pruned_clusters.append(
            {
                **cluster,
                "pois": slim_nodes,
                "hotels": hotels[:max_hotels_per_cluster],
                "events": events[:max_events_per_cluster],
            }
        )

    return {
        "duration_days": payload.get("duration_days"),
        "clusters": pruned_clusters,
        "meta": {
            **(payload.get("meta") or {}),
            "alpha_pruned": True,
            "kept_clusters": len(pruned_clusters),
        },
    }


def _hotel_pref_score(hotel: dict[str, Any], request: PackageRequest) -> int:
    facts = hotel.get("facts") or {}
    score = 0
    rating = str(request.accommodation.rating.value if request.accommodation.rating else "")
    stars = re.search(r"(\d)", rating)
    # Compare numerically: ratings arrive as 5, 5.0 or "5" across the corpus.
    if stars and int(_fact_number(hotel, "star_rating")) == int(stars.group(1)):
        score += 5
    acc_type = _norm(request.accommodation.type.value if request.accommodation.type else "")
    blob = _norm(
        f"{hotel.get('name')} {' '.join(str(w) for w in (hotel.get('why_retrieved') or []))} "
        f"{' '.join(str(a) for a in (facts.get('amenities') or []))}"
    )
    if acc_type and acc_type in blob:
        score += 4
    if "boutique" in acc_type and "boutique" in blob:
        score += 3
    return score


def _requested_stars(request: PackageRequest) -> int | None:
    match = re.search(r"(\d)", str(request.accommodation.rating.value or ""))
    return int(match.group(1)) if match else None


def _night_bases(
    clusters: list[dict[str, Any]], request: PackageRequest, nights: int
) -> list[str]:
    """Name the overnight base for each night, carrying its real star rating.

    Night N is spent where day N ends, so lodging is read off that day's own cluster;
    a global "top two hotels" list leaves a multi-area trip without saying where the
    nights were actually spent. The card's rating travels with the name, and any gap
    against the request is spelled out here — an area may simply not have the
    requested tier, and the plan has to say the tier it booked rather than the tier
    that was asked for."""
    wanted = _requested_stars(request)
    lines: list[str] = []
    for index, cluster in enumerate(clusters[:max(nights, 0)], start=1):
        cid = cluster.get("cluster_id")
        hotels = [
            h for h in (cluster.get("hotels") or [])
            if isinstance(h, dict) and h.get("name")
        ]
        if not hotels:
            lines.append(f"N{index}(C{cid}): no hotel card — state lodging is not covered")
            continue
        hotels.sort(key=lambda h: -_hotel_pref_score(h, request))
        best = hotels[0]
        stars = int(_fact_number(best, "star_rating"))
        if not stars:
            note = " (rating absent from card — claim no rating)"
        elif wanted and stars != wanted:
            note = f" ({wanted}-star unavailable in this area — say it is {stars}-star)"
        else:
            note = ""
        shown = f"{stars}-star" if stars else "unrated"
        lines.append(f"N{index}(C{cid}): {best.get('name')} [{shown}]{note}")
    return lines


def _fact_number(poi: dict[str, Any], key: str) -> float:
    try:
        return float((poi.get("facts") or {}).get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def _headline_poi(cluster: dict[str, Any]) -> str:
    """The destination's principal attraction — the site itself, not a stand-in.

    Name matching cannot find it: a site's museum or visitor centre carries the
    destination's name while the site itself does not ("Al-Khazneh" for Petra), which
    is how a free museum ends up replacing the main event. The ticketed site is what
    a visitor comes for, so the entry fee leads — and where several monuments share one
    site they also share its fee, so the tie goes to the longest visit: a gateway and the
    ruins behind it both cost 10 JOD, and only one of them is worth an afternoon. Anchor
    role, then retrieval order, settle whatever is still level."""
    best_name, best_key = "", None
    for node in cluster.get("pois") or []:
        poi = (node or {}).get("poi") or {}
        name = str(poi.get("name") or "")
        if not name:
            continue
        key = (
            -_fact_number(poi, "entry_fee"),
            -_fact_number(poi, "average_visit_minutes"),
            _role_rank(poi),
        )
        if best_key is None or key < best_key:
            best_key, best_name = key, name
    return best_name


def _must_visit_hits(clusters: list[dict[str, Any]], request: PackageRequest) -> list[str]:
    hits: list[str] = []
    for place in request.preferences.mustVisit:
        cluster = _best_cluster_for_destination(place.value, clusters)
        if cluster is None:
            hits.append(
                f"{place.value}→NOT IN EVIDENCE (still plan around preferred regions)"
            )
            continue
        headline = _headline_poi(cluster)
        cid = cluster.get("cluster_id")
        hits.append(
            f"{place.value}→lead with {headline} (cluster {cid})"
            if headline
            else f"{place.value}→cluster {cid} (theme match)"
        )
    return hits


def _mandatory_destinations(request: PackageRequest) -> list[str]:
    """preferredRegions + mustVisit, de-duplicated, corridor-ordered."""
    seen: set[str] = set()
    destinations: list[str] = []
    for item in list(request.trip.preferredRegions) + list(request.preferences.mustVisit):
        label = item.value if hasattr(item, "value") else str(item)
        key = _norm(label)
        if not key or key in seen:
            continue
        seen.add(key)
        destinations.append(label)
    return sorted(destinations, key=_corridor_index)


def _best_cluster_for_destination(
    destination: str, clusters: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Pick the strongest retrieved cluster for a destination label."""
    scored: list[tuple[int, dict[str, Any]]] = []
    for cluster in clusters:
        hay = _haystack(cluster)
        if not _matches_label(destination, hay):
            continue
        score = 10
        # Prefer POI name hits over theme-only hits.
        for node in cluster.get("pois") or []:
            poi = (node or {}).get("poi") or {}
            name = str(poi.get("name") or "")
            if name and _matches_label(destination, _norm(name)):
                score += 50
                if _role_rank(poi) == 0:
                    score += 10
        scored.append((score, cluster))
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], item[1].get("cluster_id", 0)))
    return scored[0][1]


def _destination_cluster_map(
    clusters: list[dict[str, Any]], request: PackageRequest
) -> list[str]:
    lines: list[str] = []
    for destination in _mandatory_destinations(request):
        cluster = _best_cluster_for_destination(destination, clusters)
        if not cluster:
            lines.append(f"{destination}→UNMAPPED (no matching cluster)")
            continue
        cid = cluster.get("cluster_id")
        theme = cluster.get("theme") or ""
        lines.append(f"{destination}→cluster {cid} ({theme})")
    return lines


_SAME_SITE_KM = 0.6      # closer than this on foot: parts of one attraction


def _poi_point(poi: dict[str, Any]) -> tuple[float, float] | None:
    try:
        lat, lon = float(poi.get("latitude")), float(poi.get("longitude"))
    except (TypeError, ValueError):
        return None
    return (lat, lon) if lat and lon else None


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    from math import asin, cos, radians, sin, sqrt

    p1, p2 = radians(a[0]), radians(b[0])
    dp, dl = p2 - p1, radians(b[1] - a[1])
    h = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(h))


def _same_site_groups(clusters: list[dict[str, Any]]) -> list[str]:
    """Name the POI groups that are really one attraction seen from several cards.

    A large site arrives as separate cards — an arena, a theatre, a gate inside the same
    ruins — and read literally they become separate half-hour stops, or worse, each
    other's alternatives on a ticket that already covers both. Walking distance is the
    honest test, so POIs within a few hundred metres are reported as one visit."""
    lines: list[str] = []
    for cluster in clusters:
        points: list[tuple[str, tuple[float, float]]] = []
        for node in cluster.get("pois") or []:
            poi = (node or {}).get("poi") or {}
            point = _poi_point(poi)
            if point and poi.get("name"):
                points.append((str(poi["name"]), point))
        remaining = list(points)
        while remaining:
            name, point = remaining.pop(0)
            group = [name]
            rest = []
            for other_name, other_point in remaining:
                if _km(point, other_point) <= _SAME_SITE_KM:
                    group.append(other_name)
                else:
                    rest.append((other_name, other_point))
            remaining = rest
            if len(group) > 1:
                lines.append(f"C{cluster.get('cluster_id')}: {' + '.join(group)}")
    return lines


def _cluster_label(cluster: dict[str, Any], request: PackageRequest) -> str:
    """What this cluster is here to serve, for the model's benefit."""
    for destination in _mandatory_destinations(request):
        if _matches_label(destination, _haystack(cluster)):
            return destination
    return str(cluster.get("theme") or cluster.get("cluster_id") or "area")


def _day_cluster_route(
    duration: int, request: PackageRequest, clusters: list[dict[str, Any]]
) -> str:
    """One day per retrieved cluster, in the order the retriever routed them.

    The retriever already returns about `duration` clusters, ordered as a travelable
    route and holding disjoint entities, so a day simply IS a cluster. Routing days
    through a destination→cluster map instead collapses two clusters in the same city
    onto one day-label, and two days handed the same evidence produce the same site
    twice — the repetition came from the allocation, not the model. Labels still name
    the destination each cluster serves, and a second cluster for one place is marked
    as such so its day is written as a different day out."""
    usable = [c for c in clusters if isinstance(c, dict)]
    if duration <= 0:
        duration = len(usable) or 1
    if not usable:
        return " → ".join(f"D{i + 1}:unmapped" for i in range(duration))

    labels = [_cluster_label(c, request) for c in usable]
    counts: dict[str, int] = {}
    parts: list[str] = []
    for cluster, label in zip(usable, labels):
        seen = counts.get(label, 0)
        counts[label] = seen + 1
        suffix = f" part {seen + 1}" if labels.count(label) > 1 else ""
        parts.append(f"C{cluster.get('cluster_id')}/{label}{suffix}")

    # Clusters and days normally agree; if the corpus gave fewer, spread the days
    # over what exists in order rather than dropping a day.
    if len(parts) < duration:
        parts += [parts[-1]] * (duration - len(parts))
    return " → ".join(f"D{i + 1}:{p}" for i, p in enumerate(parts[:duration]))


_SPEND_STANCE = {
    "budget": "take the cheaper of two comparable options and note the saving",
    "comfort": "spend the headroom on better-rated entities instead of leaving it idle",
    "maximize": "fit more per day while keeping the pace realistic",
    "famous": "lead each day with the best-known site in its cluster",
    "hidden": "favour the lesser-known entities the cluster offers",
    "authentic": "favour local, family-run entities where the cards say so",
    "sustainable": "favour reserves and eco-labelled entities where the cards say so",
    "family": "check every pick against the youngest traveller",
}


def build_planning_lock(payload: dict[str, Any], request: PackageRequest) -> str:
    """Short hard constraints the itinerary model must obey."""
    clusters = [c for c in (payload.get("clusters") or []) if isinstance(c, dict)]
    duration = int(payload.get("duration_days") or request.duration_days or 1)
    nights = max(duration - 1, 0)
    must_hits = _must_visit_hits(clusters, request)
    dest_map = _destination_cluster_map(clusters, request)
    day_route = _day_cluster_route(duration, request, clusters)
    night_bases = _night_bases(clusters, request, nights)
    destinations = ", ".join(_mandatory_destinations(request)) or "(none)"
    ai = request.extras.aiPriority.value
    sme = ", ".join(p.value for p in request.extras.smePreferences) or "(none)"
    budget = request.trip.totalBudget
    travelers = request.travelers
    heads = max(travelers.adults + travelers.children + travelers.seniors, 1)
    rooms = max((heads + 1) // 2, 1)
    per_day = budget / max(duration, 1)
    stance = _SPEND_STANCE.get(ai, "keep picks proportionate to the stated budget")
    same_site = _same_site_groups(clusters)

    lines = [
        "PLANNING LOCK (hard — plan OVER clusters, then write JSON):",
        f"- Fill ALL {duration} days (nights={nights}). No empty/partial days.",
        f"- Mandatory destinations (preferredRegions + mustVisit): {destinations}. "
        "Plan ONLY in these areas — any other cluster is reference material, not a day.",
        f"- Destination→cluster map: {'; '.join(dest_map) if dest_map else '(none)'}",
        f"- Day→cluster route (one day per cluster, in this order): {day_route}",
        f"- mustVisit entity lock: {'; '.join(must_hits) if must_hits else '(none)'}",
        "- Each day draws its POIs, meals and hotel from ITS OWN cluster.",
        "- No entity twice in the whole trip: a POI or restaurant used on one day cannot "
        "reappear on another, and lunch and dinner are different places. Two days in the "
        "same city are two different clusters — use each cluster's own entities.",
        "- Each day: 3 sights + lunch + dinner (5 entries, 6 max). Two sights only when the "
        "cluster has no third worth visiting, and say so. No gap over 90 minutes, no site "
        "under 45 minutes, at least 4 hours of sightseeing per full day.",
        "- activity_alternatives come from that cluster's UNUSED entities: never an entity "
        "scheduled elsewhere in the trip, and never two scheduled stops as each other's swap.",
        "- One visit, one fee (POIs within "
        f"{_SAME_SITE_KM * 1000:g} m are parts of one site): "
        + ("; ".join(same_site) if same_site else "(no such groups here)"),
        f"- Lodging requested: rating={request.accommodation.rating.value}, "
        f"type={request.accommodation.type.value}. Per-night base (night N = where day N "
        f"ends): {'; '.join(night_bases) if night_bases else '(no hotel cards — say so)'}",
        f"- Money: {budget:g} JOD covers {heads} traveller(s) for {duration} days "
        f"(≈{per_day:g} JOD/day for the whole party). Lodging = nightly rate x {nights} "
        f"night(s) x ~{rooms} room(s), arithmetic shown in the notes. aiPriority={ai} → "
        f"{stance}. SME={sme}.",
        "- Entry fees are the last thing to cut: never skip a named destination's main "
        "ticketed site to save money, and state what is left of the budget.",
        "- Names/hours/fees: EntityCards only. If a card does not carry a fact "
        "(rating, booking requirement, closing day), do not state it.",
        "- Prices: use the card value as-is, multiplied by the party size, and show the "
        'arithmetic in the tip ("10 JOD x 4"). If a card has no price, estimate from '
        'pricing_level and label it "~N JOD (estimated)".',
        "- Events are reference only: never schedule them in the itinerary or budget.",
    ]
    return "\n".join(lines)
