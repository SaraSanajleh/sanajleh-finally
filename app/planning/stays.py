"""Pick an overnight hotel by city, requested stars, type, then GPS."""

from __future__ import annotations

from app.planning.geo import airport_coords, haversine_km
from app.planning.profile import TouristProfile, requested_stars
from app.retrieval.catalog import card_matches_region
from app.retrieval.knowledge import KnowledgeCard

TYPE_HINTS: dict[str, tuple[str, ...]] = {
    "hotel": ("hotel",),
    "resort": ("resort",),
    "boutique": ("boutique",),
    "eco_lodge": ("eco", "lodge", "cabin"),
    "desert_camp": ("camp", "glamping", "bedouin"),
}


def _distance_km(card: KnowledgeCard, lat: float, lon: float) -> float:
    if card.latitude is None or card.longitude is None:
        return 999.0
    return haversine_km(card.latitude, card.longitude, lat, lon)


def card_stars(card: KnowledgeCard) -> float:
    raw = card.facts.get("star_rating")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def card_matches_stay_type(card: KnowledgeCard, wanted: str) -> bool:
    key = (wanted or "").strip().lower()
    if not key or key in {"no_pref", "unspecified", ""}:
        return True
    hints = TYPE_HINTS.get(key, (key.replace("_", " "),))
    hay = f"{card.category} {card.name} {card.facts.get('subcategory') or ''}".lower()
    return any(hint in hay for hint in hints)


def _star_sort_key(card: KnowledgeCard, wanted: float | None) -> tuple[int, float]:
    got = card_stars(card)
    if not wanted:
        return (0, -got)
    if got >= wanted:
        return (0, -got)
    if got <= 0:
        return (2, 0.0)
    return (1, wanted - got)


def pick_stay_hotel(
    hotels: list[KnowledgeCard],
    overnight_key: str,
    *,
    near_lat: float | None = None,
    near_lon: float | None = None,
    profile: TouristProfile | None = None,
) -> KnowledgeCard | None:
    eligible = [card for card in hotels if card_matches_region(card, overnight_key)] or list(hotels)
    if not eligible:
        return None
    wanted = requested_stars(profile.accommodation_rating) if profile else None
    stay_type = profile.accommodation_type if profile else ""

    def sort_key(card: KnowledgeCard) -> tuple:
        star_group, star_gap = _star_sort_key(card, wanted)
        type_miss = 0 if card_matches_stay_type(card, stay_type) else 1
        distance = (
            _distance_km(card, near_lat, near_lon)
            if near_lat is not None and near_lon is not None
            else 0.0
        )
        return (star_group, star_gap, type_miss, distance, -card.relevance, card.name)

    eligible.sort(key=sort_key)
    picked = eligible[0]
    reasons = list(picked.why_selected)
    got = card_stars(picked)
    if wanted and got >= wanted:
        note = f"{got:g}-star stay, as requested"
        if note not in reasons:
            reasons.insert(0, note)
    elif wanted and got > 0:
        note = f"No {wanted:g}-star listing here — closest listed is {got:g}-star"
        if note not in reasons:
            reasons.insert(0, note)
    elif wanted:
        note = f"Star rating is not listed for this stay (you asked for {wanted:g}-star)"
        if note not in reasons:
            reasons.insert(0, note)
    if stay_type and card_matches_stay_type(picked, stay_type):
        type_note = f"Matches {stay_type.replace('_', ' ')}"
        if type_note not in reasons:
            reasons.append(type_note)
    return picked.model_copy(update={"why_selected": reasons[:5]})


def airport_anchor(airport: str | None) -> tuple[float, float]:
    return airport_coords(airport)
