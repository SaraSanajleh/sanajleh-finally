"""Tourism ranking: geo gate, then traveler fit, then one-visit packing."""

from __future__ import annotations

from app.planning.constraints import item_is_avoided
from app.planning.geo import haversine_km
from app.planning.profile import TouristProfile
from app.planning.stays import card_matches_stay_type, card_stars
from app.retrieval.catalog import card_matches_region
from app.retrieval.knowledge import KnowledgeCard
from app.retrieval.query import DayRetrievalQuery

INTEREST_HINTS: dict[str, tuple[str, ...]] = {
    "history": ("history", "heritage", "historical", "archaeolog", "roman", "castle", "ruins"),
    "archaeology": ("archaeolog", "ruins", "roman", "nabataean", "heritage"),
    "culture": ("culture", "heritage", "museum", "local", "craft", "souk", "souq"),
    "nature": ("forest", "reserve", "trail", "wildlife", "dune", "canyon", "spring", "desert", "waterfall"),
    "hiking": ("hike", "trail", "trek", "canyon", "wadi"),
    "adventure": ("adventure", "desert", "jeep", "climb", "dive"),
    "desert": ("desert", "wadi rum", "bedouin", "dune"),
    "food": ("food", "cuisine", "restaurant", "mansaf", "mezze"),
    "beaches": ("beach", "aqaba", "red sea", "snorkel", "dive"),
    "wellness": ("wellness", "spa", "dead sea", "float"),
    "photography": ("photo", "view", "panoram", "scenic", "sunset", "iconic", "arch"),
    "religious_sites": (
        "church",
        "mosque",
        "biblical",
        "shrine",
        "monastery",
        "cathedral",
        "orthodox",
        "prophet",
        "mosaic",
        "nebo",
        "baptism",
        "chapel",
    ),
    "museums": ("museum", "gallery", "exhibit", "collection"),
    "art": ("art", "gallery", "mosaic", "craft"),
    "shopping": ("souk", "souq", "bazaar", "market"),
    "scenic_views": ("view", "panoram", "scenic", "lookout", "sunset"),
    "local_experiences": ("local", "village", "community", "craft"),
    "eco_tourism": ("eco", "reserve", "nature", "forest"),
    "wildlife": ("wildlife", "bird", "reserve"),
    "camping": ("camp", "desert", "cabin"),
}

# Headline sites a first-time visitor should not miss. Components of these
# sites are the same ticket, not extra stops.
LANDMARKS: dict[str, tuple[str, ...]] = {
    "jerash": ("jerash archaeological site", "hadrian", "oval plaza"),
    "ajloun": ("ajloun castle", "ajloun forest", "mar elias"),
    "petra": ("petra archaeological", "treasury", "al-khazneh", "siq", "royal tombs"),
    "wadi rum": ("um frouth", "khazali", "sand dune", "lawrence", "burdah", "um ad dami", "seven pillars"),
    "aqaba": ("aqaba fort", "south beach", "aqaba archaeological"),
    "dead sea": ("dead sea", "panoramic", "mujib", "amman beach"),
    "amman": ("citadel", "roman theater", "rainbow street", "jordan museum"),
    "madaba": ("map mosaic", "st. george", "st george", "mount nebo", "mosaic map", "archaeological park"),
    "karak": ("karak castle", "crusader", "al-karak castle"),
}

SITE_FAMILIES: dict[str, tuple[str, ...]] = {
    "jerash_archaeological": (
        "jerash archaeological",
        "hippodrome of jerash",
        "south theater of jerash",
        "north theater of jerash",
        "nymphaeum of jerash",
        "north gate of jerash",
        "macellum of jerash",
        "cathedral of jerash",
        "east baths of jerash",
        "propylaea of jerash",
        "oval plaza",
        "hadrian",
        "temple of artemis",
        "cardo",
    ),
    "petra_park": (
        "petra archaeological",
        "petra visitor",
        "siq",
        "treasury",
        "al-khazneh",
        "monastery",
        "ad-deir",
        "royal tombs",
        "street of facades",
    ),
    "ajloun_castle": ("ajloun castle", "qal'at ar-rabad", "qalat ar-rabad"),
    "ajloun_forest": ("ajloun forest", "soap house", "roe deer"),
    "wadi_rum_protected": ("wadi rum protected area",),
    "mujib_reserve": ("mujib biosphere", "wadi mujib", "mujib siq"),
}

UMBRELLA_TOKENS = (
    "archaeological site",
    "archaeological park",
    "protected area",
    "forest reserve",
    "nature reserve",
)

SERVICE_TOKENS = (
    "visitor center",
    "ticket office",
    "rest house",
    "information center",
)

# Civic leftovers a tourist itinerary should not treat as highlights.
FILLER_TOKENS = (
    "municipal stadium",
    "stadium",
    "sports complex",
    "athletic events",
    "football match",
    "commercial market",
    "commercial hub",
    "shopping mall",
    "retail plaza",
    "children's play",
    "family recreational",
)


def belongs_to_region(card: KnowledgeCard, key: str) -> bool:
    return card_matches_region(card, key)


def _hay(card: KnowledgeCard) -> str:
    return " ".join(
        [
            card.name,
            card.summary,
            card.category,
            card.city,
            card.region,
            " ".join(str(v) for v in (card.facts.get("themes") or [])),
            " ".join(str(v) for v in (card.facts.get("suitable_for") or [])),
            " ".join(str(v) for v in (card.facts.get("cuisine_types") or [])),
            str(card.facts.get("subcategory") or ""),
        ]
    ).lower()


def interest_hits_for(card: KnowledgeCard, interests: list[str]) -> list[str]:
    hay = _hay(card)
    hits: list[str] = []
    for interest in interests:
        key = (interest or "").lower()
        hints = INTEREST_HINTS.get(key, (key.replace("_", " "),))
        if any(hint in hay for hint in hints):
            hits.append(interest)
    return hits


def is_filler_poi(card: KnowledgeCard, interests: list[str] | None = None) -> bool:
    """Stadiums, malls, and playgrounds are not a cultural day."""
    if card.entity_type != "poi":
        return False
    hay = _hay(card)
    wanted = {(item or "").lower() for item in (interests or [])}
    if any(token in hay for token in FILLER_TOKENS):
        if "shopping" in wanted and any(
            token in hay for token in ("market", "souk", "souq", "bazaar", "mall")
        ):
            return False
        return True
    return False


def site_family(card: KnowledgeCard) -> str:
    name = card.name.lower()
    for family, members in SITE_FAMILIES.items():
        if any(token in name for token in members):
            return family
    return ""


def _visit_minutes(card: KnowledgeCard, default: int = 0) -> int:
    raw = card.facts.get("visit_minutes")
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return default


def _is_umbrella(card: KnowledgeCard) -> bool:
    name = card.name.lower()
    if _is_service(card):
        return False
    return any(token in name for token in UMBRELLA_TOKENS)


def _is_service(card: KnowledgeCard) -> bool:
    if card.entity_type != "poi":
        return False
    name = card.name.lower()
    return any(token in name for token in SERVICE_TOKENS)


def score_card(
    card: KnowledgeCard,
    profile: TouristProfile,
    query: DayRetrievalQuery,
) -> KnowledgeCard | None:
    if card.item_id in set(query.used_ids):
        return None
    if item_is_avoided(card.name, card.region, card.city, profile):
        return None
    if card.entity_type == "hotel":
        gate = query.overnight_key or query.region_key
        if not belongs_to_region(card, gate):
            return None
    else:
        visit_keys = list(query.visit_keys) or [query.region_key]
        if not any(belongs_to_region(card, key) for key in visit_keys):
            return None
    if is_filler_poi(card, query.interests):
        return None

    hay = _hay(card)
    reasons: list[str] = [f"In {query.region}"]
    score = 0.28

    retrieved = bool(card.facts.get("retrieved")) or any(
        reason not in {"local_tourism_catalog"} for reason in (card.why_retrieved or [])
    )
    if retrieved and card.entity_type == "poi":
        score += 0.22
        if card.why_retrieved:
            reasons.append(str(card.why_retrieved[0]))
        else:
            reasons.append("Retrieved for this trip")
        rank = card.facts.get("retrieval_rank")
        try:
            rank_n = int(rank)
        except (TypeError, ValueError):
            rank_n = 99
        if 0 <= rank_n < 8:
            score += 0.03 * (8 - rank_n) / 8
        if str(card.facts.get("role") or "").lower() == "anchor":
            score += 0.04

    visit_keys = list(query.visit_keys) or [query.region_key]
    landmark_hints = tuple(hint for key in visit_keys for hint in LANDMARKS.get(key, ()))
    landmark_hits = [hint for hint in landmark_hints if hint in hay]
    if landmark_hits and not _is_service(card):
        boost = 0.30 if query.stay_index == 0 else 0.12
        score += boost
        reasons.append(f"A must-see in {query.region}")
    elif query.stay_index >= 1 and card.entity_type == "poi" and not _is_service(card):
        score += 0.10
        reasons.append("A second day to go beyond the main site")

    if query.is_must_visit and query.region_key in hay:
        score += 0.10

    interest_hits = interest_hits_for(card, query.interests)
    if interest_hits:
        score += min(0.28, 0.10 * len(interest_hits))
        reasons.append("Matches " + ", ".join(interest_hits[:3]))
    elif query.interests and card.entity_type == "poi" and not landmark_hits and not _is_umbrella(card):
        score -= 0.18

    audience = " ".join(str(v) for v in (card.facts.get("suitable_for") or [])).lower()
    if query.has_children and "famil" in audience:
        score += 0.08
        reasons.append("Works well for families")
    if query.group_type == "couple" and "couple" in audience:
        score += 0.04
    if query.limited_mobility and "access" in hay:
        score += 0.08
        reasons.append("Easier to visit with limited walking")

    indoor = (card.indoor_outdoor or str(card.facts.get("indoor_outdoor") or "")).lower()
    if query.heat_risk and card.entity_type == "poi":
        if "indoor" in indoor:
            score += 0.05
            reasons.append("Indoor option on a hot day")
        if "outdoor" in indoor and "castle" not in hay and "archaeolog" not in hay:
            score -= 0.03

    if card.entity_type == "restaurant" and query.cuisine:
        if any(c.lower().split()[0] in hay for c in query.cuisine):
            score += 0.10
            reasons.append("Matches preferred cuisine")

    if card.entity_type == "hotel":
        got = card_stars(card)
        wanted = query.hotel_stars
        if wanted and got >= wanted:
            score += 0.32
            reasons.append(f"{got:g}-star, as requested")
        elif wanted and got > 0:
            gap = wanted - got
            score += max(0.0, 0.12 - 0.08 * gap)
            reasons.append(f"{got:g}-star listing")
        elif wanted:
            score -= 0.04
        if query.accommodation_type and card_matches_stay_type(card, query.accommodation_type):
            score += 0.12
            reasons.append(f"Matches {query.accommodation_type.replace('_', ' ')}")
        elif query.accommodation_type:
            score -= 0.06

    minutes = _visit_minutes(card)
    if card.entity_type == "poi" and minutes >= 75:
        score += 0.05
    if _is_umbrella(card) and query.stay_index == 0:
        score += 0.08
    if _is_service(card) and card.entity_type == "poi":
        score -= 0.20
        reasons.append("Orientation stop, not the main experience")

    updated = card.model_copy(
        update={
            "relevance": min(1.0, max(score, 0.0)),
            "why_selected": reasons[:5],
        }
    )
    return updated


def _near(left: KnowledgeCard, right: KnowledgeCard, km: float) -> bool:
    if left.latitude is None or right.latitude is None:
        return False
    if left.longitude is None or right.longitude is None:
        return False
    return haversine_km(left.latitude, left.longitude, right.latitude, right.longitude) <= km


def _pick_site_winner(members: list[KnowledgeCard]) -> KnowledgeCard:
    members = sorted(
        members,
        key=lambda card: (
            0 if _is_umbrella(card) else 1,
            -card.relevance,
            -_visit_minutes(card),
            card.name,
        ),
    )
    winner = members[0]
    if len(members) == 1:
        return winner
    extra = "One visit covering the nearby monuments"
    reasons = list(winner.why_selected)
    if extra not in reasons:
        reasons.append(extra)
    return winner.model_copy(update={"why_selected": reasons[:5]})


def collapse_same_site(cards: list[KnowledgeCard]) -> list[KnowledgeCard]:
    """Hippodrome + South Theater + the archaeological site are one Jerash ticket."""
    if len(cards) <= 1:
        return list(cards)
    groups: list[list[KnowledgeCard]] = []
    for card in sorted(cards, key=lambda item: -item.relevance):
        family = site_family(card)
        placed = False
        for group in groups:
            seed = group[0]
            same_family = family and family == site_family(seed)
            nearby = card.entity_type == seed.entity_type and _near(card, seed, 0.55)
            if same_family or nearby:
                group.append(card)
                placed = True
                break
        if not placed:
            groups.append([card])
    return [_pick_site_winner(group) for group in groups]


def _category_key(card: KnowledgeCard) -> str:
    return str(card.facts.get("subcategory") or card.category or card.entity_type).lower()


def _distance_km(left: KnowledgeCard, right: KnowledgeCard) -> float:
    mapped = (left.facts.get("nearby_poi_km") or {}).get(right.item_id)
    if mapped is None:
        mapped = (right.facts.get("nearby_poi_km") or {}).get(left.item_id)
    try:
        if mapped is not None:
            return float(mapped)
    except (TypeError, ValueError):
        pass
    if left.latitude is None or right.latitude is None:
        return 40.0
    if left.longitude is None or right.longitude is None:
        return 40.0
    return haversine_km(left.latitude, left.longitude, right.latitude, right.longitude)


def pack_nearby(
    cards: list[KnowledgeCard],
    limit: int,
    query: DayRetrievalQuery | None = None,
) -> list[KnowledgeCard]:
    """Walk a coherent neighborhood. Do not pad the day with civic leftovers."""
    if limit <= 0:
        return []
    collapsed = collapse_same_site(cards)
    if not collapsed:
        return []
    interests = list(query.interests) if query else []
    collapsed = [card for card in collapsed if not is_filler_poi(card, interests)]
    if not collapsed:
        return []
    collapsed.sort(key=lambda item: (-item.relevance, item.name))
    retrieved = [
        card
        for card in collapsed
        if card.facts.get("retrieved") and not _is_service(card)
    ]
    seed = retrieved[0] if retrieved else next(
        (card for card in collapsed if not _is_service(card)),
        collapsed[0],
    )
    picked = [seed]
    remaining = [card for card in collapsed if card.item_id != seed.item_id]
    landmark_hints = ()
    if query:
        visit_keys = list(query.visit_keys) or [query.region_key]
        landmark_hints = tuple(hint for key in visit_keys for hint in LANDMARKS.get(key, ()))

    def theme_rank(card: KnowledgeCard) -> int:
        if not interests:
            return 0
        if interest_hits_for(card, interests):
            return 0
        if any(hint in _hay(card) for hint in landmark_hints):
            return 0
        return 1

    while len(picked) < limit and remaining:
        remaining.sort(
            key=lambda card: (
                1 if _is_service(card) else 0,
                0 if card.facts.get("retrieved") else 1,
                theme_rank(card),
                0 if min(_distance_km(anchor, card) for anchor in picked) <= 8 else 1,
                -card.relevance,
                min(_distance_km(anchor, card) for anchor in picked),
                card.name,
            )
        )
        picked.append(remaining.pop(0))
    return picked[:limit]


def diversify(
    cards: list[KnowledgeCard],
    limit: int,
    query: DayRetrievalQuery | None = None,
) -> list[KnowledgeCard]:
    return pack_nearby(cards, limit, query)


def rank_cards(
    cards: list[KnowledgeCard],
    profile: TouristProfile,
    query: DayRetrievalQuery,
    limit: int,
) -> list[KnowledgeCard]:
    scored: list[KnowledgeCard] = []
    seen: set[str] = set()
    for card in cards:
        if card.item_id in seen:
            continue
        ranked = score_card(card, profile, query)
        if ranked is None:
            continue
        seen.add(card.item_id)
        scored.append(ranked)
    scored.sort(key=lambda item: (-item.relevance, item.name))
    if scored and scored[0].entity_type == "hotel":
        return scored[:limit]
    return diversify(scored, limit, query)


def prefer_near(
    candidates: list[KnowledgeCard],
    anchors: list[KnowledgeCard],
    limit: int,
) -> list[KnowledgeCard]:
    """Prefer restaurants/hotels that sit next to the day's chosen sights."""
    if not candidates:
        return []
    if not anchors:
        return candidates[:limit]

    def closeness(card: KnowledgeCard) -> float:
        distances = [_near(card, anchor, 12) for anchor in anchors if anchor.latitude is not None]
        if any(distances):
            return 1.0
        return 0.0

    ordered = sorted(candidates, key=lambda card: (-closeness(card), -card.relevance, card.name))
    return ordered[:limit]


def prefer_slot_restaurants(
    pois: list[KnowledgeCard],
    restaurants: list[KnowledgeCard],
    limit: int,
) -> list[KnowledgeCard]:
    """Use the restaurant the retriever attached to each sight, then nearby listings."""
    if limit <= 0 or not restaurants:
        return []
    by_id = {card.item_id: card for card in restaurants}
    front: list[KnowledgeCard] = []
    seen: set[str] = set()
    for poi in pois:
        for rest_id in poi.facts.get("nearby_restaurant_ids") or []:
            card = by_id.get(str(rest_id))
            if card is None or card.item_id in seen:
                continue
            seen.add(card.item_id)
            front.append(card)
            if len(front) >= limit:
                return front
    leftover = [card for card in restaurants if card.item_id not in seen]
    return front + prefer_near(leftover, pois, limit - len(front))
