"""Tourism RAG pipeline: query → geo-gated recall → rank → pack."""

from __future__ import annotations

from typing import Any

from app.config.settings import AppSettings, get_app_settings
from app.context.models import PlanningContext
from app.planning.geo import centroid_for, haversine_km, venue_name_key
from app.planning.profile import TouristProfile
from app.retrieval.catalog import REGION_NEIGHBORS, card_matches_region, cards_for_region
from app.retrieval.knowledge import DayShortlist, KnowledgeCard, RetrievedKnowledge, compress_knowledge, overlay_retrieved_evidence
from app.retrieval.query import DayRetrievalQuery, build_day_query
from app.retrieval.ranker import LANDMARKS, collapse_same_site, prefer_near, prefer_slot_restaurants, rank_cards, site_family

CLOCK_POIS = 8
CLOCK_MINUTES = 300
FILL_RADIUS_KM = 45.0


def _restaurant_name_key(card: KnowledgeCard) -> str:
    return venue_name_key(card.name)


def _dedupe_restaurant_names(cards: list[KnowledgeCard]) -> list[KnowledgeCard]:
    seen: set[str] = set()
    out: list[KnowledgeCard] = []
    for card in cards:
        key = _restaurant_name_key(card)
        if key in seen:
            continue
        seen.add(key)
        out.append(card)
    return out


def _breakfast_cards(cards: list[KnowledgeCard]) -> list[KnowledgeCard]:
    tokens = ("cafe", "café", "breakfast", "bakery", "bistro")
    return [
        card
        for card in cards
        if any(token in f"{card.name} {card.category}".lower() for token in tokens)
    ]


def _card_minutes(card: KnowledgeCard, default: int = 60) -> int:
    raw = card.facts.get("visit_minutes")
    try:
        value = int(round(float(raw)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _clock_short(pois: list[KnowledgeCard]) -> bool:
    """A day with three long listings is still thin — we need enough stops."""
    if len(pois) < CLOCK_POIS:
        return True
    capped = [min(_card_minutes(card), 75) for card in pois]
    return sum(capped) < CLOCK_MINUTES


def _within_radius(card: KnowledgeCard, origin: tuple[float, float] | None, radius: float) -> bool:
    if origin is None or card.latitude is None or card.longitude is None:
        return False
    return haversine_km(origin[0], origin[1], card.latitude, card.longitude) <= radius


def _is_region_landmark(card: KnowledgeCard, key: str) -> bool:
    hay = f"{card.name} {card.summary} {card.city}".lower()
    return any(hint in hay for hint in LANDMARKS.get(key, ()))


def _closer_to_current_than_later(
    card: KnowledgeCard,
    current_key: str,
    later_keys: set[str],
) -> bool:
    """A fill-in must sit on this day's turf, not the next day's city."""
    if card.latitude is None or card.longitude is None:
        return False
    current = centroid_for(current_key)
    if current is None:
        return True
    d_cur = haversine_km(card.latitude, card.longitude, current[0], current[1])
    for later in later_keys:
        pin = centroid_for(later)
        if pin is None:
            continue
        d_later = haversine_km(card.latitude, card.longitude, pin[0], pin[1])
        if d_later < d_cur:
            return False
    return True


def _fill_thin_pois(
    query: DayRetrievalQuery,
    recalled: RetrievedKnowledge,
    profile: TouristProfile,
    region_key: str,
    used_ids: set[str],
    need: int,
    later_keys: set[str] | None = None,
    already: list[KnowledgeCard] | None = None,
) -> list[KnowledgeCard]:
    """Borrow nearby listed places to fill a thin day, not another day's headline sights."""
    if need <= 0:
        return []
    reserved = {key for key in (later_keys or set()) if key and key != region_key}
    taken_families = {site_family(card) for card in (already or []) if site_family(card)}
    out: list[KnowledgeCard] = []
    origin = centroid_for(region_key)
    neighbors = list(REGION_NEIGHBORS.get(region_key, set()))
    if origin is not None:
        neighbors.sort(
            key=lambda nb: (
                haversine_km(origin[0], origin[1], *(centroid_for(nb) or origin))
                if centroid_for(nb)
                else 9e9
            )
        )

    def _ok(card: KnowledgeCard) -> bool:
        fam = site_family(card)
        if fam and (fam in taken_families or any(site_family(item) == fam for item in out)):
            return False
        return (
            not any(_is_region_landmark(card, key) for key in reserved)
            and _within_radius(card, origin, FILL_RADIUS_KM)
            and _closer_to_current_than_later(card, region_key, reserved)
        )

    for neighbor in neighbors:
        if len(out) >= need:
            break
        nb_query = query.model_copy(
            update={
                "region_key": neighbor,
                "region": neighbor.title(),
                "visit_keys": [neighbor],
                "used_ids": sorted(used_ids | {card.item_id for card in out}),
            }
        )
        pool = _recall_for_day(nb_query, recalled.pois, "poi", neighbor)
        ranked = [
            card
            for card in rank_cards(pool, profile, nb_query, max(need - len(out) + 16, 16))
            if _ok(card)
        ]
        substantial = [card for card in ranked if _card_minutes(card) >= 40]
        out = _merge(out, substantial)
        if len(out) < need:
            out = _merge(out, [card for card in ranked if _card_minutes(card) >= 25])
    return out[:need]


def _cover_meal_slots(ranked: list[KnowledgeCard], attached: list[KnowledgeCard], limit: int) -> list[KnowledgeCard]:
    breakfast = _breakfast_cards(ranked)[:2]
    leftover = [card for card in ranked if card.item_id not in {item.item_id for item in breakfast}]
    lunch = leftover[:3]
    dinner = list(reversed(leftover))[:3]
    return _dedupe_restaurant_names(_merge(breakfast, lunch, dinner, attached, ranked))[: max(limit, 10)]


def _merge(*groups: list[KnowledgeCard]) -> list[KnowledgeCard]:
    seen: set[str] = set()
    out: list[KnowledgeCard] = []
    for group in groups:
        for card in group:
            if card.item_id in seen:
                continue
            seen.add(card.item_id)
            out.append(card)
    return out


def _merge_catalog_and_retrieved(
    catalog: list[KnowledgeCard],
    retrieved: list[KnowledgeCard],
) -> list[KnowledgeCard]:
    """Catalog is ground truth. Retriever evidence overlays the same IDs."""
    by_id = {card.item_id: card for card in catalog}
    seen: set[str] = set()
    out: list[KnowledgeCard] = []
    for extra in retrieved:
        base = by_id.get(extra.item_id)
        if base is not None:
            out.append(overlay_retrieved_evidence(base, extra))
        else:
            facts = dict(extra.facts)
            facts["retrieved"] = True
            out.append(extra.model_copy(update={"facts": facts}))
        seen.add(extra.item_id)
    for card in catalog:
        if card.item_id not in seen:
            out.append(card)
    return out


def _recall_for_day(
    query: DayRetrievalQuery,
    retrieved: list[KnowledgeCard],
    entity_type: str,
    region_key: str | None = None,
) -> list[KnowledgeCard]:
    key = region_key or query.region_key
    catalog = cards_for_region(key, entity_type)
    extras = [
        card
        for card in retrieved
        if card.entity_type == entity_type and card_matches_region(card, key)
    ]
    return _merge_catalog_and_retrieved(catalog, extras)


def compose_trip_knowledge(
    raw: dict[str, Any],
    profile: TouristProfile,
    context: PlanningContext,
    settings: AppSettings | None = None,
) -> RetrievedKnowledge:
    """Plan from the locked day regions. Retriever recall is optional evidence."""
    settings = settings or get_app_settings()
    recalled = compress_knowledge(raw, profile, settings)
    intents = context.day_intents or []
    heat = context.climate.heat_risk == "high"
    shortlists: list[DayShortlist] = []
    used_ids: set[str] = set()
    warnings: list[str] = []
    prev_overnight = ""

    for index, intent in enumerate(intents):
        query = build_day_query(
            profile,
            intent,
            heat_risk=heat,
            need_hotel=index < profile.nights,
            used_ids=used_ids,
        )
        hotel_key = intent.overnight_key or intent.region_key
        waking_in = prev_overnight or hotel_key
        checking_in = query.need_hotel and hotel_key != prev_overnight
        visit_keys = [intent.region_key]
        if getattr(intent, "paired_key", ""):
            visit_keys.append(intent.paired_key)
        rest_keys = list(dict.fromkeys([*visit_keys, hotel_key, waking_in]))
        pool_pois = _merge(
            *[_recall_for_day(query, recalled.pois, "poi", key) for key in visit_keys]
        )
        pool_rests = _merge(
            *[_recall_for_day(query, recalled.restaurants, "restaurant", key) for key in rest_keys]
        )
        pool_hotels = (
            _recall_for_day(query, recalled.hotels, "hotel", hotel_key) if checking_in else []
        )

        extra = 3 if intent.stay_index else 2
        if intent.is_arrival_day:
            poi_limit = max(intent.sights + 4, 6) if intent.allow_arrival_activities else 0
        else:
            poi_limit = max(intent.sights + extra, CLOCK_POIS) if intent.sights else CLOCK_POIS
        pois = rank_cards(pool_pois, profile, query, max(poi_limit, CLOCK_POIS))
        if not intent.is_arrival_day and _clock_short(pois):
            later_keys = {
                later.region_key
                for later in intents[index + 1 :]
                if later.region_key
            }
            need = max(CLOCK_POIS - len(pois), 4)
            pois = _merge(
                pois,
                _fill_thin_pois(
                    query,
                    recalled,
                    profile,
                    intent.region_key,
                    used_ids | {card.item_id for card in pois},
                    need,
                    later_keys=later_keys,
                    already=pois,
                ),
            )
            pois = collapse_same_site(pois)
        ranked_rests = rank_cards(pool_rests, profile, query, max(intent.meals + extra, 10))
        restaurants = _cover_meal_slots(
            ranked_rests,
            prefer_slot_restaurants(pois, ranked_rests, max(intent.meals + 2, 4)),
            max(intent.meals + extra, 10),
        )
        hotel_query = query.model_copy(
            update={
                "region_key": hotel_key,
                "region": intent.overnight_region or intent.region,
                "visit_keys": [hotel_key],
            }
        )
        if hotel_key:
            base_rests = rank_cards(
                _recall_for_day(query, recalled.restaurants, "restaurant", hotel_key),
                profile,
                hotel_query,
                6,
            )
            restaurants = _dedupe_restaurant_names(_merge(restaurants, base_rests))
        if waking_in and waking_in not in visit_keys:
            wake_query = query.model_copy(
                update={
                    "region_key": waking_in,
                    "region": waking_in.title(),
                    "visit_keys": [waking_in],
                }
            )
            wake_rests = rank_cards(
                _recall_for_day(query, recalled.restaurants, "restaurant", waking_in),
                profile,
                wake_query,
                4,
            )
            restaurants = _dedupe_restaurant_names(_merge(wake_rests, restaurants))
        if not intent.is_arrival_day and len(restaurants) < 3:
            restaurants = _dedupe_restaurant_names(_merge(restaurants, pool_rests))[:12]
        ranked_hotels = rank_cards(pool_hotels, profile, hotel_query, 8) if checking_in else []
        hotels = (
            ranked_hotels
            if query.hotel_stars or not pois
            else prefer_near(ranked_hotels, pois, 4)
        )
        if intent.sights and not pool_pois:
            warnings.append(f"Few listed sights were found for {intent.region}.")
        if not pool_rests:
            warnings.append(f"Few listed restaurants were found for {intent.region}.")
        if checking_in and not pool_hotels:
            warnings.append(f"No listed hotel was found for the night in {intent.overnight_region or intent.region}.")

        shortlists.append(
            DayShortlist(
                day=intent.day,
                region=intent.region,
                region_key=intent.region_key,
                theme=intent.theme,
                pois=pois,
                restaurants=restaurants,
                hotels=hotels,
            )
        )
        if not intent.is_arrival_day:
            used_ids.update(card.item_id for card in pois[:3])
        if hotel_key:
            prev_overnight = hotel_key

    all_pois = _merge(*[item.pois for item in shortlists])
    all_restaurants = _merge(*[item.restaurants for item in shortlists])
    all_hotels = _merge(*[item.hotels for item in shortlists])

    status = recalled.status
    if shortlists and any(item.pois for item in shortlists):
        status = "ok" if status in {"ok", "unknown", "unavailable", "disabled", "thin"} else status
    elif not all_pois:
        status = recalled.status if recalled.status != "ok" else "thin"

    return RetrievedKnowledge(
        status=status,
        duration_days=profile.duration_days,
        planning_lock=(
            "Each day may use only that day's shortlist. "
            "IDs are frozen. Do not pull another region's leftovers."
        ),
        pois=all_pois,
        restaurants=all_restaurants,
        hotels=all_hotels,
        clusters=[
            {
                "cluster_id": item.day,
                "theme": item.theme,
                "summary": f"{item.region} day {item.day}",
                "poi_names": [card.name for card in item.pois],
            }
            for item in shortlists
        ],
        warnings=warnings,
        day_shortlists=shortlists,
    )
