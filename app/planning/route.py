"""Lock each trip day to a real requested region, with airport-aware stays."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from app.planning.geo import (
    arrival_city_key,
    centroid_for,
    haversine_km,
    region_half,
    region_key,
)
from app.planning.profile import TouristProfile

CORRIDOR: tuple[str, ...] = (
    "irbid",
    "ajloun",
    "jerash",
    "amman",
    "zarqa",
    "balqa",
    "salt",
    "madaba",
    "dead sea",
    "karak",
    "tafilah",
    "petra",
    "wadi musa",
    "wadi rum",
    "maan",
    "ma'an",
    "aqaba",
)

DISPLAY_NAME: dict[str, str] = {
    "irbid": "Irbid",
    "ajloun": "Ajloun",
    "jerash": "Jerash",
    "amman": "Amman",
    "zarqa": "Zarqa",
    "balqa": "Balqa",
    "salt": "As-Salt",
    "madaba": "Madaba",
    "dead sea": "Dead Sea",
    "karak": "Karak",
    "tafilah": "Tafilah",
    "petra": "Petra",
    "wadi musa": "Petra",
    "wadi rum": "Wadi Rum",
    "maan": "Petra",
    "ma'an": "Petra",
    "aqaba": "Aqaba",
}

HALF_LABEL = {"north_center": "north and center", "south": "south"}

# Two destinations share a day only when they are actually close.
SAME_DAY_KM = 30.0
NEARBY_EXPAND_KM = 100.0
DAY_TRIP_HOME_KM = 60.0
MUST_MAX_DAYS = 2
CLASSIC_DAY_PAIRS = {
    frozenset({"jerash", "ajloun"}),
    frozenset({"madaba", "dead sea"}),
    frozenset({"amman", "madaba"}),
}
TOURIST_DESTS: tuple[str, ...] = (
    "irbid",
    "ajloun",
    "jerash",
    "amman",
    "madaba",
    "dead sea",
    "karak",
    "tafilah",
    "petra",
    "wadi rum",
    "aqaba",
    "salt",
)


@dataclass(frozen=True)
class DayRoute:
    day: int
    region: str
    region_key: str
    is_must_visit: bool
    stay_index: int
    overnight_key: str
    overnight_region: str
    is_arrival_day: bool = False
    stay_style: str = "in_region"
    focus_half: str = ""
    dropped_half: str = ""
    paired_key: str = ""


def _corridor_index(key: str) -> int:
    try:
        return CORRIDOR.index(key)
    except ValueError:
        return 80


def _flow_index(key: str, airport: str) -> int:
    """Drive along the country from the airport, not the other way around."""
    idx = _corridor_index(key)
    if (airport or "AMM").upper() == "AQJ":
        return -idx
    return idx


def requested_destinations(profile: TouristProfile) -> list[tuple[str, str, bool]]:
    """Unique (label, key, must_visit) from must-visit + preferred regions only."""
    seen: set[str] = set()
    dests: list[tuple[str, str, bool]] = []
    must_keys = {region_key(item) for item in profile.must_visit if region_key(item)}
    for raw in [*profile.must_visit, *profile.preferred_regions]:
        key = region_key(raw)
        if not key or key in seen:
            continue
        seen.add(key)
        dests.append((DISPLAY_NAME.get(key, raw), key, key in must_keys))
    dests.sort(key=lambda item: (_corridor_index(item[1]), item[0]))
    return dests


def _cluster_region(cluster: dict[str, Any]) -> str:
    counts: Counter[str] = Counter()
    for node in cluster.get("pois") or []:
        if not isinstance(node, dict):
            continue
        poi = node.get("poi") if isinstance(node.get("poi"), dict) else node
        region = str((poi or {}).get("region") or "").strip()
        if region:
            counts[region] += 1
    if counts:
        return counts.most_common(1)[0][0]
    theme = str(cluster.get("theme") or "")
    return theme.split("·")[0].strip()


def destinations_from_clusters(raw: dict[str, Any] | None) -> list[tuple[str, str, bool]]:
    """When the wizard named no places, turn interest-matched clusters into a route."""
    seen: set[str] = set()
    dests: list[tuple[str, str, bool]] = []
    for cluster in (raw or {}).get("clusters") or []:
        if not isinstance(cluster, dict):
            continue
        key = region_key(_cluster_region(cluster))
        if not key or key in seen:
            continue
        seen.add(key)
        dests.append((DISPLAY_NAME.get(key, key.title()), key, False))
    dests.sort(key=lambda item: (_corridor_index(item[1]), item[0]))
    return dests


def interest_region_scores(
    profile: TouristProfile,
    raw: dict[str, Any] | None = None,
) -> dict[str, float]:
    """How well each catalog region matches the traveler's interests."""
    from app.retrieval.catalog import load_tourism_catalog
    from app.retrieval.ranker import LANDMARKS, interest_hits_for, is_filler_poi

    scores: dict[str, list[float]] = {}
    for card in load_tourism_catalog():
        if card.entity_type != "poi" or not card.region_key:
            continue
        if is_filler_poi(card, profile.interests):
            continue
        hits = interest_hits_for(card, profile.interests)
        if not hits:
            continue
        key = card.region_key
        value = 1.0 + 0.35 * len(hits)
        hay = f"{card.name} {card.summary} {card.category}".lower()
        if any(hint in hay for hint in LANDMARKS.get(key, ())):
            value += 2.5
        scores.setdefault(key, []).append(value)

    totals = {
        key: sum(sorted(values, reverse=True)[:8])
        for key, values in scores.items()
    }
    for _, key, _ in destinations_from_clusters(raw):
        if key in totals:
            totals[key] += 1.2
    return totals


def destinations_from_interests(
    profile: TouristProfile,
    raw: dict[str, Any] | None = None,
) -> list[tuple[str, str, bool]]:
    """Open trip: follow interests, then keep the chosen places near each other."""
    totals = interest_region_scores(profile, raw)
    if not totals:
        return destinations_from_clusters(raw)

    ranked = sorted(totals, key=lambda key: (-totals[key], _corridor_index(key)))
    airport = (profile.arrival_airport or "AMM").upper()
    arrival_half = region_half(arrival_city_key(airport))
    explore = max(getattr(profile, "exploration_days", None) or profile.duration_days, 1)
    local = [key for key in ranked if region_half(key) == arrival_half]
    if explore <= 5 and local and totals[local[0]] >= 0.85 * totals[ranked[0]]:
        ordered = local
    else:
        half = region_half(ranked[0])
        ordered = [key for key in ranked if region_half(key) == half] or ranked

    want = min(3, explore)
    picked = ordered[:want]
    return [(DISPLAY_NAME.get(key, key.title()), key, False) for key in picked]


def apply_open_trip_evidence(
    profile: TouristProfile,
    raw: dict[str, Any] | None,
) -> tuple[TouristProfile, list[tuple[str, str, bool]]]:
    """Wizard regions win. Open trips follow retriever clusters, then catalog interests."""
    if profile.region_keys:
        return profile, []
    dests = destinations_from_clusters(raw)
    if not dests:
        dests = destinations_from_interests(profile, raw)
    if not dests:
        return profile, []
    return profile.model_copy(update={"region_keys": [key for _, key, _ in dests]}), dests


def _half_score(dests: list[tuple[str, str, bool]], half: str, airport: str) -> tuple[int, int, int]:
    members = [item for item in dests if region_half(item[1]) == half]
    musts = sum(1 for item in members if item[2])
    affinity = 1 if (airport in {"AQJ"} and half == "south") or (airport != "AQJ" and half == "north_center") else 0
    return (musts, len(members), affinity)


def choose_focus_half(
    dests: list[tuple[str, str, bool]],
    profile: TouristProfile,
) -> tuple[str, str]:
    """Named wizard dests are kept. One-half locking is only for inferred trips."""
    halves = {region_half(key) for _, key, _ in dests}
    if len(halves) <= 1:
        only = next(iter(halves), "north_center")
        return only, ""
    named = bool(profile.must_visit or profile.preferred_regions)
    if named:
        return "mixed", ""
    if (getattr(profile, "exploration_days", None) or profile.duration_days) > 5:
        return "mixed", ""
    airport = (profile.arrival_airport or "AMM").upper()
    north = _half_score(dests, "north_center", airport)
    south = _half_score(dests, "south", airport)
    if south > north:
        return "south", "north_center"
    return "north_center", "south"


def _on_the_way(key: str, arrival_key: str, focus_keys: list[str]) -> bool:
    """Keep a dest on the other half only if it sits on the drive to the nearest focus."""
    if not key or not arrival_key or not focus_keys or key == arrival_key:
        return False
    nearest = min(focus_keys, key=lambda focus: _km(arrival_key, focus))
    direct = _km(arrival_key, nearest)
    if direct <= 1 or direct >= 900:
        return False
    if _km(arrival_key, key) >= direct:
        return False
    via = _km(arrival_key, key) + _km(key, nearest)
    return via / direct <= 1.30


def _filter_dests(
    dests: list[tuple[str, str, bool]],
    focus: str,
    arrival_key: str = "",
) -> list[tuple[str, str, bool]]:
    if focus in {"", "mixed"}:
        return dests
    kept = [item for item in dests if region_half(item[1]) == focus]
    if not kept:
        return dests
    focus_keys = [key for _, key, _ in kept]
    extras = [
        item
        for item in dests
        if item[1] not in set(focus_keys) and _on_the_way(item[1], arrival_key, focus_keys)
    ]
    if extras:
        kept = kept + extras
        kept.sort(key=lambda item: (_corridor_index(item[1]), item[0]))
    return kept


def _km(a: str, b: str) -> float:
    ca, cb = centroid_for(a), centroid_for(b)
    if not ca or not cb:
        return 999.0
    return haversine_km(ca[0], ca[1], cb[0], cb[1])


def _can_share_day(a: str, b: str) -> bool:
    if not a or not b or a == b:
        return False
    if frozenset({a, b}) in CLASSIC_DAY_PAIRS:
        return True
    return _km(a, b) <= SAME_DAY_KM


def _spread(keys: list[str]) -> float:
    if len(keys) <= 1:
        return 0.0
    dists = [_km(a, b) for i, a in enumerate(keys) for b in keys[i + 1 :]]
    return sum(dists) / len(dists)


def _avoid_keys(profile: TouristProfile | None) -> set[str]:
    if not profile:
        return set()
    return {region_key(item) for item in profile.places_to_avoid if region_key(item)}


def _compact(
    musts: list[tuple[str, str, bool]],
    extras: list[tuple[str, str, bool]],
    days: int,
) -> tuple[list[tuple[str, str, bool]], list[tuple[str, str, bool]]]:
    """Keep musts. Fill remaining days with the tightest extra cluster. Return unused extras."""
    from itertools import combinations

    if days <= 0:
        return [], musts + extras
    if len(musts) >= days:
        return musts[:days], extras + musts[days:]
    need = days - len(musts)
    if need >= len(extras):
        return list(musts) + list(extras), []
    best: list[tuple[str, str, bool]] | None = None
    best_spread = 1e18
    for combo in combinations(extras, need):
        chosen = list(musts) + list(combo)
        spread = _spread([item[1] for item in chosen])
        if spread < best_spread:
            best_spread = spread
            best = chosen
    chosen = best or (list(musts) + extras[:need])
    picked = {item[1] for item in chosen}
    unused = [item for item in extras if item[1] not in picked]
    return chosen, unused


def _attach_pairs(
    chosen: list[tuple[str, str, bool]],
    unused: list[tuple[str, str, bool]],
) -> list[tuple[str, str, bool, str]]:
    """If a dropped dest is close to a kept one, visit both on the same day."""
    taken: set[str] = set()
    pairs: dict[str, tuple[str, str, bool]] = {}
    for item in unused:
        best_key = ""
        best_d = 1e18
        for label, key, must in chosen:
            if key in taken:
                continue
            if not _can_share_day(item[1], key):
                continue
            dist = _km(item[1], key)
            if dist < best_d:
                best_d = dist
                best_key = key
        if best_key:
            pairs[best_key] = item
            taken.add(best_key)
    slots: list[tuple[str, str, bool, str]] = []
    for label, key, must in chosen:
        paired = pairs.get(key)
        if paired:
            slots.append((label, key, must or paired[2], paired[1]))
        else:
            slots.append((label, key, must, ""))
    return slots


def _nearby_interest_dests(
    profile: TouristProfile,
    anchors: list[str],
    *,
    exclude: set[str],
    focus: str,
    limit: int,
) -> list[tuple[str, str, bool]]:
    """Extra days: nearby places that fit the traveler, not another copy of the must-visit."""
    if limit <= 0:
        return []
    totals = interest_region_scores(profile)
    avoid = _avoid_keys(profile)
    ranked = sorted(
        set(TOURIST_DESTS) | set(totals),
        key=lambda key: (
            min((_km(key, anchor) for anchor in anchors), default=0.0) if anchors else 0.0,
            -totals.get(key, 0.0),
            _corridor_index(key),
        ),
    )
    out: list[tuple[str, str, bool]] = []
    for key in ranked:
        if key in exclude or key in avoid:
            continue
        if focus not in {"", "mixed"} and region_half(key) != focus:
            continue
        if anchors and min(_km(key, anchor) for anchor in anchors) > NEARBY_EXPAND_KM:
            continue
        out.append((DISPLAY_NAME.get(key, key.title()), key, False))
        if len(out) >= limit:
            break
    return out


def _allocate(
    dests: list[tuple[str, str, bool]],
    days: int,
    *,
    profile: TouristProfile | None = None,
    focus: str = "",
    expand: bool = True,
) -> list[tuple[str, str, bool, int, str]]:
    """Must-visits first (up to two days). Named explore dests always get a day when one remains."""
    if days <= 0 or not dests:
        return []

    musts = [item for item in dests if item[2]]
    extras = [item for item in dests if not item[2]]
    chosen, unused = _compact(musts, extras, days)
    slots = _attach_pairs(chosen, unused)
    airport = (profile.arrival_airport or "AMM").upper() if profile else "AMM"
    slots.sort(key=lambda item: (_flow_index(item[1], airport), item[0]))
    weights = [1] * len(slots)

    def leftover() -> int:
        return days - sum(weights)

    def bump(indices: list[int], cap: int | None = None) -> None:
        step = 0
        while leftover() > 0 and indices:
            i = indices[step % len(indices)]
            if cap is not None and weights[i] >= cap:
                indices = [j for j in indices if not (cap is not None and weights[j] >= cap)]
                if not indices:
                    break
                step = 0
                continue
            weights[i] += 1
            step += 1

    named_must = [i for i, slot in enumerate(slots) if slot[2]]
    named_explore = [i for i, slot in enumerate(slots) if not slot[2]]
    bump(named_must, cap=MUST_MAX_DAYS)
    bump(named_explore, cap=MUST_MAX_DAYS)

    if leftover() > 0 and expand and profile:
        exclude = {slot[1] for slot in slots} | {slot[3] for slot in slots if slot[3]}
        nearby = _nearby_interest_dests(
            profile,
            [slot[1] for slot in slots],
            exclude=exclude,
            focus=focus,
            limit=leftover(),
        )
        for item in nearby:
            slots.append((item[0], item[1], False, ""))
            weights.append(1)

    bump([i for i, slot in enumerate(slots) if not slot[2]], cap=MUST_MAX_DAYS)

    out: list[tuple[str, str, bool, int, str]] = []
    for (label, key, must, paired), weight in zip(slots, weights):
        for stay in range(weight):
            out.append((label, key, must, stay, paired if stay == 0 else ""))
    return out[:days]


PREFERRED_SOUTH_BASES: tuple[str, ...] = ("petra", "aqaba", "wadi rum")
RESORT_STAYS = {"dead sea"}


def _south_hub(
    keys: list[str],
    counts: Counter[str],
    profile: TouristProfile,
    airport: str,
) -> str:
    unique = list(dict.fromkeys(keys))
    if not unique:
        return ""
    if len(unique) == 1:
        return unique[0]
    stay_type = (profile.accommodation_type or "").strip().lower()
    if stay_type == "desert_camp" and "wadi rum" in unique:
        return "wadi rum"
    if stay_type == "resort" and "aqaba" in unique:
        return "aqaba"
    if airport == "AQJ" and "aqaba" in unique:
        return "aqaba"
    best = max(counts[key] for key in unique)
    tied = {key for key in unique if counts[key] == best}
    for preferred in PREFERRED_SOUTH_BASES:
        if preferred in tied:
            return preferred
    for preferred in PREFERRED_SOUTH_BASES:
        if preferred in unique:
            return preferred
    return unique[0]


def _assign_overnights(
    allocated: list[tuple[str, str, bool, int, str]],
    *,
    airport: str,
    arrival_key: str,
    profile: TouristProfile,
) -> list[tuple[str, str, bool, int, str, str]]:
    """Share one bed across nearby days. Do not change hotels every night."""
    keys = [item[1] for item in allocated]
    counts = Counter(keys)
    south_keys = [key for key in keys if region_half(key) == "south"]
    south_hub = _south_hub(south_keys, counts, profile, airport)
    north_hub = arrival_key if region_half(arrival_key) == "north_center" else "amman"
    south_must_bases = {
        key
        for _, key, must, _, _ in allocated
        if must and counts[key] >= 2 and region_half(key) == "south"
    }
    two_south_bases = len(south_must_bases) >= 2
    rows: list[tuple[str, str, bool, int, str, str]] = []
    prev = ""
    for label, key, must, stay, paired in allocated:
        half = region_half(key)
        if key in RESORT_STAYS:
            overnight = key
        elif half == "south":
            if two_south_bases and counts[key] >= 2:
                overnight = key
            elif prev and _km(key, prev) <= DAY_TRIP_HOME_KM:
                overnight = prev
            else:
                overnight = south_hub or key
        elif counts[key] >= 2:
            overnight = key
        elif prev and _km(key, prev) <= DAY_TRIP_HOME_KM:
            overnight = prev
        else:
            overnight = north_hub
        rows.append((label, key, must, stay, overnight, paired))
        prev = overnight
    return rows


def plan_day_route(
    profile: TouristProfile,
    inferred_dests: list[tuple[str, str, bool]] | None = None,
) -> list[DayRoute]:
    """Arrival is its own phase at the airport city. Exploration days follow."""
    dests = requested_destinations(profile)
    if not dests and inferred_dests:
        dests = list(inferred_dests)
    days = max(profile.duration_days, 1)
    airport = (profile.arrival_airport or "AMM").upper()
    arrival_key = arrival_city_key(airport)
    arrival_label = DISPLAY_NAME.get(arrival_key, "Amman")
    focus, dropped = choose_focus_half(dests, profile)
    dests = _filter_dests(dests, focus, arrival_key)

    arrival_stop = DayRoute(
        day=1,
        region=arrival_label,
        region_key=arrival_key,
        is_must_visit=False,
        stay_index=0,
        overnight_key=arrival_key,
        overnight_region=arrival_label,
        is_arrival_day=True,
        stay_style="arrival",
        focus_half=focus,
        dropped_half=dropped,
    )
    if days == 1:
        return [arrival_stop]

    remaining_dests = list(dests)
    if not inferred_dests:
        remaining_dests = [item for item in dests if item[1] != arrival_key] or dests
    allocated = _assign_overnights(
        _allocate(
            remaining_dests,
            days - 1,
            profile=profile,
            focus=focus,
            expand=not inferred_dests,
        ),
        airport=airport,
        arrival_key=arrival_key,
        profile=profile,
    )
    if not allocated:
        return [
            DayRoute(
                day=i + 1,
                region=arrival_label,
                region_key=arrival_key,
                is_must_visit=False,
                stay_index=i,
                overnight_key=arrival_key,
                overnight_region=arrival_label,
                is_arrival_day=i == 0,
                stay_style="arrival" if i == 0 else "in_region",
                focus_half=focus,
                dropped_half=dropped,
            )
            for i in range(days)
        ]

    route = [arrival_stop]
    for label, key, must, stay, overnight, paired in allocated:
        overnight_label = DISPLAY_NAME.get(overnight, overnight.title())
        stay_style = "day_trip" if overnight != key else "in_region"
        pair_label = DISPLAY_NAME.get(paired, paired.title()) if paired else ""
        region = f"{label} & {pair_label}" if paired and stay == 0 else label
        route.append(
            DayRoute(
                day=len(route) + 1,
                region=region,
                region_key=key,
                is_must_visit=must,
                stay_index=stay,
                overnight_key=overnight,
                overnight_region=overnight_label,
                is_arrival_day=False,
                stay_style=stay_style,
                focus_half=focus,
                dropped_half=dropped,
                paired_key=paired if stay == 0 else "",
            )
        )
    return route[:days]
