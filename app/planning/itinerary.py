"""Build a grounded itinerary from context + ranked RAG + trip SME team."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4
import re

from app.context.models import DayIntent, PlanningContext
from app.context.builder import tourist_planning_reason, planner_notes, _route_phrase
from app.planning.constraints import evaluate_constraints
from app.planning.profile import TouristProfile, budget_band, requested_stars
from app.planning.arrival import arrival_beats, arrival_transport_note, plan_arrival
from app.planning.meal_clock import (
    MEAL_REASON,
    MEAL_SLOT,
    ExploringDayClock,
    build_exploring_day_clock,
)
from app.planning.geo import centroid_for, haversine_km, region_key, venue_name_key
from app.planning.route import DISPLAY_NAME
from app.planning.stays import airport_anchor, card_stars, pick_stay_hotel
from app.retrieval.knowledge import DayShortlist, KnowledgeCard, RetrievedKnowledge
from app.schemas.response.package_response import TourismPackage
from app.sme.models import SMEMatch


# Travel between stops is not visit time. POI length is average_visit_minutes.
TRANSFER_GAP_MINUTES = 15
MAX_IDLE_MINUTES = 35
MAX_WINDOW_POIS = 5
MEAL_STOP_MINUTES = 60
AFTERNOON_SIGHTS_END = datetime(2000, 1, 1, 17, 30)


def _minutes(card: KnowledgeCard, default: int = 60) -> int:
    """POI clock is average_visit_minutes from the listing / retriever."""
    raw = card.facts.get("visit_minutes")
    try:
        value = int(round(float(raw)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _meal_stop_minutes(card: KnowledgeCard) -> int:
    """A sit-down meal on the clock is an hour, not a lingering listing."""
    listed = _minutes(card)
    return min(listed, MEAL_STOP_MINUTES) if listed else MEAL_STOP_MINUTES


def _pack_minutes(card: KnowledgeCard, cursor: datetime, limit: datetime) -> int:
    """Use the listed visit length. Do not invent a shorter stop."""
    listed = _minutes(card)
    start = _wait_open(cursor, card)
    leftover = int((limit - start).total_seconds() // 60)
    closes = _parse_clock(card.facts.get("closing_hours"))
    if closes:
        leftover = min(leftover, int((closes - start).total_seconds() // 60))
    if listed > leftover:
        return 0
    return listed


def _can_pack(cursor: datetime, card: KnowledgeCard, limit: datetime) -> bool:
    start = _wait_open(cursor, card)
    if start >= limit:
        return False
    wait = int((start - cursor).total_seconds() // 60)
    if wait > MAX_IDLE_MINUTES:
        return False
    return _pack_minutes(card, cursor, limit) > 0


def _amount(value: object) -> float | None:
    if value in (None, "", [], "not_available"):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group()) if match else None


def _cost(card: KnowledgeCard) -> str:
    currency = str(card.facts.get("currency") or "JOD")
    if card.entity_type == "hotel":
        amount = _amount(card.facts.get("night_price"))
        if amount is None:
            return "not_available"
        return f"{amount:g} {currency} / night"
    amount = _amount(card.facts.get("entry_fee"))
    if amount is None:
        amount = _amount(card.facts.get("meal_price"))
    if amount is None:
        return "not_available"
    return f"{amount:g} {currency}"


def _clock(start: datetime, minutes: int) -> tuple[str, str, datetime]:
    end = start + timedelta(minutes=minutes)
    return start.strftime("%H:%M"), end.strftime("%H:%M"), end


def _fits(cursor: datetime, minutes: int, limit: datetime) -> bool:
    return cursor + timedelta(minutes=minutes) <= limit


def _parse_clock(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text or ":" not in text:
        return None
    try:
        hour_s, minute_s = text.split(":", 1)
        return datetime(2000, 1, 1, int(hour_s), int(minute_s[:2]))
    except (TypeError, ValueError):
        return None


def _wait_open(cursor: datetime, card: KnowledgeCard) -> datetime:
    opens = _parse_clock(card.facts.get("opening_hours"))
    if opens and cursor < opens:
        return opens
    return cursor


def _fits_listing(
    cursor: datetime,
    card: KnowledgeCard,
    limit: datetime,
    minutes: int | None = None,
) -> bool:
    start = _wait_open(cursor, card)
    duration = minutes if minutes is not None else _minutes(card)
    if not _fits(start, duration, limit):
        return False
    closes = _parse_clock(card.facts.get("closing_hours"))
    return not (closes and start + timedelta(minutes=duration) > closes)


def _description(card: KnowledgeCard) -> str:
    if card.summary:
        return card.summary
    highlights = card.facts.get("highlights") or []
    if highlights:
        return str(highlights[0])
    return f"{card.name} in {card.city or card.region}."


def _schedule_item(
    card: KnowledgeCard,
    *,
    time: str,
    end: str,
    slot: str,
    item_type: str,
    duration_minutes: int | None = None,
) -> dict[str, Any]:
    dataset = {"poi": "pois", "restaurant": "restaurants", "hotel": "hotels"}.get(item_type, item_type)
    minutes = duration_minutes if duration_minutes is not None else _minutes(card)
    return {
        "time": time,
        "end_time": end,
        "slot": slot,
        "type": item_type,
        "item_id": card.item_id,
        "name": card.name,
        "duration_minutes": minutes,
        "location": card.city or card.region,
        "coordinates": {
            "latitude": card.latitude,
            "longitude": card.longitude,
            "precision": card.geo_precision,
        }
        if card.latitude is not None
        else None,
        "description": _description(card),
        "reason": "; ".join(card.why_selected or card.why_retrieved[:3]) or f"Grounded {item_type} in this day's region.",
        "matched_preferences": list(card.why_selected),
        "estimated_cost": _cost(card),
        "source": {"dataset": dataset, "record_id": card.item_id},
        "confidence": "high",
    }


def _place(
    card: KnowledgeCard,
    cursor: datetime,
    *,
    item_type: str,
    slot: str | None = None,
    reason: str | None = None,
    gap: int = TRANSFER_GAP_MINUTES,
    minutes: int | None = None,
    wait_open: bool = True,
) -> tuple[dict[str, Any], datetime]:
    minutes = minutes if minutes is not None else _minutes(card)
    if wait_open:
        cursor = _wait_open(cursor, card)
    start, end, done = _clock(cursor, minutes)
    if slot is None:
        slot = "morning" if cursor.hour < 13 else "afternoon"
        if item_type == "restaurant" and cursor.hour >= 16:
            slot = "evening"
    item = _schedule_item(
        card,
        time=start,
        end=end,
        slot=slot,
        item_type=item_type,
        duration_minutes=minutes,
    )
    if reason:
        item["reason"] = reason
    return item, done + timedelta(minutes=gap)


def sme_payload(match: SMEMatch) -> dict[str, Any]:
    record = match.record
    known = record.known_for()
    why = match.reasons[0] if match.reasons else (known[0] if known else "")
    return {
        "sme_id": record.sme_id,
        "sme_type": record.sme_type,
        "name": record.name,
        "role": match.role,
        "location": record.city or record.region,
        "experience_type": ", ".join(record.specializations[:3]),
        "match_score": round(match.score, 3),
        "reason": why,
        "matched_because": match.reasons,
        "known_for": known,
        "specializations": record.specializations,
        "languages": record.languages,
        "experience_years": record.experience_years,
        "destinations_covered": record.destinations_covered,
        "covers_regions": match.covers_regions,
        "package_role": match.package_role or match.role,
        "specs": record.spec_rows(),
        "min_price": record.min_price,
        "max_price": record.max_price,
        "pricing_model": record.pricing_model,
        "currency": record.currency,
        "source": {
            "dataset": "sme_guides" if record.sme_type == "tour_guide" else "sme_operators",
            "record_id": record.sme_id,
        },
        "coordinates": {
            "latitude": record.latitude,
            "longitude": record.longitude,
            "precision": record.geo_precision,
        }
        if record.latitude is not None
        else None,
    }


def _pick_outdoor_first(pois: list[KnowledgeCard], heat: bool) -> list[KnowledgeCard]:
    if not heat:
        return list(pois)
    outdoor: list[KnowledgeCard] = []
    indoor: list[KnowledgeCard] = []
    for card in pois:
        label = (card.indoor_outdoor or str(card.facts.get("indoor_outdoor") or "")).lower()
        if "indoor" in label or "museum" in card.name.lower() or card.category.lower() == "museum":
            indoor.append(card)
        else:
            outdoor.append(card)
    return outdoor + indoor


def _unused(cards: list[KnowledgeCard], used: set[str], limit: int) -> list[KnowledgeCard]:
    picked: list[KnowledgeCard] = []
    for card in cards:
        if card.item_id in used:
            continue
        picked.append(card)
        used.add(card.item_id)
        if len(picked) >= limit:
            break
    return picked


def _stay_item(card: KnowledgeCard, *, time: str = "", end: str = "", reason: str) -> dict[str, Any]:
    item = _schedule_item(card, time=time, end=end, slot="overnight", item_type="hotel")
    item["reason"] = reason
    item["duration_minutes"] = None
    return item


def _stay_reason(card: KnowledgeCard, intent: DayIntent) -> str:
    base = (
        f"Overnight stay in {intent.overnight_region or intent.region}. "
        "This is your hotel, not an activity."
    )
    extra = next(
        (note for note in card.why_selected if "star" in note.lower() or "matches" in note.lower()),
        "",
    )
    return f"{base} {extra}".strip()


def _note_stay_gap(
    hotel: KnowledgeCard,
    intent: DayIntent,
    profile: TouristProfile,
    stay_notes: list[str],
) -> None:
    wanted = requested_stars(profile.accommodation_rating)
    got = card_stars(hotel)
    place = intent.overnight_region or intent.region
    if wanted and got and got < wanted:
        stay_notes.append(
            f"No {wanted:g}-star hotel is listed in {place}; using {got:g}-star {hotel.name}."
        )
    elif wanted and got <= 0:
        stay_notes.append(
            f"{hotel.name} in {place} has no listed star rating (you asked for {wanted:g}-star)."
        )


def _transport_note(intent: DayIntent, check_in: bool) -> str:
    if intent.is_arrival_day:
        return f"Land in {intent.region}, eat nearby, then rest at your hotel."
    if check_in:
        return f"This evening you check in to your hotel in {intent.overnight_region or intent.region}."
    if intent.stay_style == "day_trip":
        return f"Come back to your hotel in {intent.overnight_region} to sleep."
    return f"Stay overnight in {intent.overnight_region or intent.region}."


def _card_region_key(card: KnowledgeCard) -> str:
    return card.region_key or region_key(card.city) or region_key(card.region)


def _pick_meal(
    restaurants: list[KnowledgeCard],
    meal_label: str,
    used: set[str],
    *,
    visit_key: str = "",
    overnight_key: str = "",
    also_key: str = "",
    woke_in: str = "",
) -> KnowledgeCard | None:
    ordered = _meal_candidates(
        restaurants,
        meal_label,
        used,
        visit_key=visit_key,
        overnight_key=overnight_key,
        also_key=also_key,
        woke_in=woke_in,
    )
    return ordered[0] if ordered else None


def _prefer_fresh_meals(
    cards: list[KnowledgeCard],
    avoid_names: set[str] | None,
) -> list[KnowledgeCard]:
    if not avoid_names:
        return cards
    fresh = [card for card in cards if _meal_name_key(card) not in avoid_names]
    repeat = [card for card in cards if _meal_name_key(card) in avoid_names]
    return fresh + repeat


def _meal_candidates(
    restaurants: list[KnowledgeCard],
    meal_label: str,
    used: set[str],
    *,
    visit_key: str = "",
    overnight_key: str = "",
    also_key: str = "",
    woke_in: str = "",
    avoid_names: set[str] | None = None,
) -> list[KnowledgeCard]:
    nightlife = ("pub", "bar", "nightclub", "cocktail", "lounge")
    breakfasty = ("cafe", "café", "breakfast", "bakery", "bistro")
    ranked = [card for card in restaurants if card.item_id not in used]
    visit_keys = {key for key in (visit_key, also_key) if key}
    if meal_label == "breakfast" and woke_in:
        home = [card for card in ranked if _card_region_key(card) == woke_in]
        ranked = home or ranked
    elif overnight_key and visit_keys and overnight_key not in visit_keys:
        if meal_label == "dinner":
            home = [card for card in ranked if _card_region_key(card) == overnight_key]
            ranked = home or ranked
        else:
            here = [card for card in ranked if _card_region_key(card) in visit_keys]
            ranked = here or ranked
    if not ranked:
        return []
    if meal_label == "breakfast":
        cafes = [
            card
            for card in ranked
            if any(token in f"{card.name} {card.category}".lower() for token in breakfasty)
        ]
        early = [
            card
            for card in ranked
            if (_parse_clock(card.facts.get("opening_hours")) or datetime(2000, 1, 1, 8, 0))
            <= datetime(2000, 1, 1, 9, 30)
        ]
        sober = [
            card
            for card in ranked
            if not any(token in f"{card.name} {card.category}".lower() for token in nightlife)
        ]
        ordered: list[KnowledgeCard] = []
        seen: set[str] = set()
        for card in [*(cafes or []), *(early or []), *(sober or []), *ranked]:
            if card.item_id in seen:
                continue
            seen.add(card.item_id)
            ordered.append(card)
        return _prefer_fresh_meals(ordered, avoid_names)
    if meal_label == "lunch":
        sober = [
            card
            for card in ranked
            if not any(token in f"{card.name} {card.category}".lower() for token in nightlife)
        ]
        return _prefer_fresh_meals(sober or ranked, avoid_names)
    return _prefer_fresh_meals(ranked, avoid_names)


def _pick_arrival_meal(
    restaurants: list[KnowledgeCard],
    meal_label: str,
    used: set[str],
    *,
    at: datetime,
    limit: datetime,
) -> KnowledgeCard | None:
    """Food near the hotel that is actually open now — not a dinner place at lunch."""
    nightlife = ("pub", "bar", "nightclub", "cocktail", "lounge")
    breakfasty = ("cafe", "café", "breakfast", "bakery", "bistro")
    ranked = [card for card in restaurants if card.item_id not in used]
    if meal_label in {"breakfast", "lunch"}:
        sober = [
            card
            for card in ranked
            if not any(token in f"{card.name} {card.category}".lower() for token in nightlife)
        ]
        ranked = sober or ranked
    meal_window = min(limit, at + timedelta(minutes=90))
    open_now = [
        card
        for card in ranked
        if ( _wait_open(at, card) - at ).total_seconds() <= 20 * 60
        and _fits_listing(at, card, meal_window)
    ]
    compact = [card for card in open_now if _minutes(card) <= 75]
    pool = compact or open_now
    if not pool:
        return None
    if meal_label == "breakfast":
        cafes = [
            card
            for card in pool
            if any(token in f"{card.name} {card.category}".lower() for token in breakfasty)
        ]
        return (cafes or pool)[0]
    return pool[0]


def _idle_minutes(cursor: datetime, target: datetime) -> int:
    if cursor >= target:
        return 0
    return int((target - cursor).total_seconds() // 60)


def _at_meal(
    cursor: datetime,
    label: str,
    *,
    day_clock: ExploringDayClock,
) -> datetime:
    """Eat within the day's window; vary the target per plan/day."""
    earliest = day_clock.meal_earliest(label)
    latest = day_clock.meal_latest(label)
    preferred = day_clock.meal_target(label)
    if cursor < earliest:
        return min(max(preferred, earliest), latest)
    if cursor >= preferred:
        return min(cursor, latest)
    if _idle_minutes(cursor, preferred) <= 30:
        return min(preferred, latest)
    return min(cursor, latest)


def _drive_minutes(from_key: str, to_key: str) -> int:
    if not from_key or not to_key or from_key == to_key:
        return 0
    start = centroid_for(from_key)
    end = centroid_for(to_key)
    if start is None or end is None:
        return 60
    km = haversine_km(start[0], start[1], end[0], end[1])
    return max(30, int(km / 55 * 60) + 15)


def _meal_name_key(card: KnowledgeCard) -> str:
    return venue_name_key(card.name)


def _scheduled_meal_names(schedule: list[dict[str, Any]]) -> set[str]:
    return {
        venue_name_key(str(item.get("name") or ""))
        for item in schedule
        if item.get("type") == "restaurant"
    }


def _serve_meal(
    restaurants: list[KnowledgeCard],
    cursor: datetime,
    label: str,
    used_ids: set[str],
    schedule: list[dict[str, Any]],
    *,
    day_clock: ExploringDayClock,
    visit_key: str = "",
    overnight_key: str = "",
    also_key: str = "",
    woke_in: str = "",
    loose: bool = False,
    avoid_names: set[str] | None = None,
    allow_repeat: bool = False,
) -> tuple[datetime, list[KnowledgeCard]]:
    meal_at = _at_meal(cursor, label, day_clock=day_clock)
    meal_latest = day_clock.meal_latest(label)
    seen_names = _scheduled_meal_names(schedule)
    scored: list[tuple[int, KnowledgeCard]] = []
    for meal in _meal_candidates(
        restaurants,
        label,
        used_ids,
        visit_key=visit_key,
        overnight_key=overnight_key,
        also_key=also_key,
        woke_in=woke_in,
        avoid_names=avoid_names,
    ):
        if not allow_repeat and _meal_name_key(meal) in seen_names:
            continue
        start = meal_at if loose else _wait_open(meal_at, meal)
        if start > meal_latest:
            continue
        if not loose and not _fits_listing(start, meal, meal_latest, minutes=_meal_stop_minutes(meal)):
            continue
        wait = max(0, int((start - meal_at).total_seconds() // 60))
        scored.append((wait, meal))
    if not scored:
        return cursor, restaurants
    scored.sort(key=lambda row: (row[0], row[1].name))
    meal = scored[0][1]
    used_ids.add(meal.item_id)
    item, done = _place(
        meal,
        meal_at,
        item_type="restaurant",
        slot=MEAL_SLOT[label],
        reason=MEAL_REASON[label],
        minutes=_meal_stop_minutes(meal),
        wait_open=not loose,
    )
    schedule.append(item)
    return done, [card for card in restaurants if card.item_id != meal.item_id]


def _meal_count(schedule: list[dict[str, Any]]) -> int:
    return sum(1 for item in schedule if item.get("type") == "restaurant")


def _force_meal(
    restaurants: list[KnowledgeCard],
    cursor: datetime,
    label: str,
    used_ids: set[str],
    schedule: list[dict[str, Any]],
    **kwargs: Any,
) -> tuple[datetime, list[KnowledgeCard]]:
    """Last resort: serve the meal even if hours or names are imperfect."""
    return _serve_meal(
        restaurants,
        cursor,
        label,
        used_ids,
        schedule,
        loose=True,
        allow_repeat=True,
        **kwargs,
    )


def _ensure_meal(
    restaurants: list[KnowledgeCard],
    cursor: datetime,
    label: str,
    used_ids: set[str],
    schedule: list[dict[str, Any]],
    **kwargs: Any,
) -> tuple[datetime, list[KnowledgeCard]]:
    """Always try to put breakfast, lunch, and dinner on the clock."""
    pool = list(restaurants)
    before = _meal_count(schedule)
    cursor, left = _serve_meal(
        pool, cursor, label, used_ids, schedule, loose=False, **kwargs
    )
    if _meal_count(schedule) == before:
        cursor, left = _serve_meal(
            pool, cursor, label, used_ids, schedule, loose=True, **kwargs
        )
    if _meal_count(schedule) == before:
        cursor, left = _serve_meal(
            pool, cursor, label, set(), schedule, loose=True, **kwargs
        )
    if _meal_count(schedule) == before:
        cursor, left = _force_meal(pool, cursor, label, set(), schedule, **kwargs)
    return cursor, left


def _pack_sights(
    pois: list[KnowledgeCard],
    cursor: datetime,
    limit: datetime,
    remaining: int,
    used_ids: set[str],
    schedule: list[dict[str, Any]],
) -> tuple[datetime, int]:
    packed = 0
    floor = max(remaining, 0)
    while packed < min(floor, MAX_WINDOW_POIS):
        leftover = [poi for poi in pois if poi.item_id not in used_ids]
        pick = next((poi for poi in leftover if _can_pack(cursor, poi, limit)), None)
        if pick is None:
            break
        minutes = _pack_minutes(pick, cursor, limit)
        used_ids.add(pick.item_id)
        item, cursor = _place(pick, cursor, item_type="poi", minutes=minutes)
        schedule.append(item)
        packed += 1
    return cursor, packed


def _last_coords(schedule: list[dict[str, Any]]) -> tuple[float, float] | None:
    for item in reversed(schedule):
        coords = item.get("coordinates") or {}
        lat, lon = coords.get("latitude"), coords.get("longitude")
        if lat is not None and lon is not None:
            return float(lat), float(lon)
    return None


def _best_gap_fill(
    pois: list[KnowledgeCard],
    cursor: datetime,
    limit: datetime,
    used_ids: set[str],
    here: tuple[float, float] | None = None,
) -> KnowledgeCard | None:
    """Pick a nearby unused sight whose listed visit actually fits the hole."""
    ranked: list[tuple[int, float, int, KnowledgeCard]] = []
    for poi in pois:
        if poi.item_id in used_ids:
            continue
        if not _can_pack(cursor, poi, limit):
            continue
        start = _wait_open(cursor, poi)
        wait = max(0, int((start - cursor).total_seconds() // 60))
        minutes = _pack_minutes(poi, cursor, limit)
        dist = 0.0
        if here is not None and poi.latitude is not None and poi.longitude is not None:
            dist = haversine_km(here[0], here[1], poi.latitude, poi.longitude)
        ranked.append((wait, dist, minutes, poi))
    if not ranked:
        return None
    ranked.sort(key=lambda row: (row[0], row[1], row[2]))
    return ranked[0][3]


def _fill_until(
    pois: list[KnowledgeCard],
    cursor: datetime,
    limit: datetime,
    target: datetime,
    used_ids: set[str],
    schedule: list[dict[str, Any]],
    *,
    reserve: int = 0,
) -> datetime:
    """Keep placing listed sights while the next meal would leave a long empty wait."""
    while _idle_minutes(cursor, target) >= MAX_IDLE_MINUTES and cursor < limit:
        leftover = [card for card in pois if card.item_id not in used_ids]
        if len(leftover) <= reserve:
            break
        pick = _best_gap_fill(leftover, cursor, limit, used_ids, _last_coords(schedule))
        if pick is None:
            break
        used_ids.add(pick.item_id)
        minutes = _pack_minutes(pick, cursor, limit)
        item, cursor = _place(pick, cursor, item_type="poi", minutes=minutes)
        schedule.append(item)
    return cursor


def _arrival_summary(plan, intent: DayIntent, names: list[str]) -> str:
    city = intent.region
    if plan.window == "overnight":
        extra = f" After you rest, the remaining day stays in {city}: {', '.join(names[:3])}." if names else " Keep the afternoon easy."
        return f"You land before dawn in {city}. Sleep first, then breakfast.{extra}"
    if plan.window == "daytime":
        extra = f" Then a short same-city plan: {', '.join(names[:3])}." if names else ""
        return f"Arrival in {city}: food, rest, then whatever daylight is left nearby.{extra}"
    if plan.window == "twilight":
        extra = f" {names[0]} only if evening remains." if names else " A quiet first evening."
        return f"Afternoon/evening arrival in {city}: eat and rest first.{extra}"
    return f"Late arrival in {city}: eat if you can, then sleep. Exploring starts tomorrow."


def _build_arrival_day(
    intent: DayIntent,
    shortlist: DayShortlist | None,
    *,
    check_in: bool,
    airport: str,
    used_ids: set[str],
    profile: TouristProfile,
    stay_notes: list[str],
    heat: bool = False,
) -> dict[str, Any]:
    restaurants = list(shortlist.restaurants) if shortlist else []
    raw_pois = _pick_outdoor_first(list(shortlist.pois) if shortlist else [], heat)
    hotels = list(shortlist.hotels) if shortlist else []
    plan = plan_arrival(intent.arrival_time or profile.arrival_time, profile.trip_pace, airport)
    schedule: list[dict[str, Any]] = []
    hotel = None
    if check_in:
        near_lat, near_lon = airport_anchor(airport)
        hotel = pick_stay_hotel(
            hotels,
            intent.overnight_key or intent.region_key,
            near_lat=near_lat,
            near_lon=near_lon,
            profile=profile,
        )
        if hotel:
            _note_stay_gap(hotel, intent, profile, stay_notes)

    cursor: datetime | None = None
    touring_end = datetime(2000, 1, 1, plan.latest_activity_hour, 0)
    for beat in arrival_beats(plan):
        if cursor is None:
            cursor = beat.start
        elif beat.kind == "hotel" and beat.start > cursor:
            cursor = beat.start
        elif schedule and schedule[-1]["type"] == "hotel" and beat.start > cursor:
            cursor = beat.start
        if beat.kind == "meal":
            if cursor is None:
                continue
            meal = _pick_arrival_meal(
                restaurants,
                beat.meal_label or plan.meal_label,
                used_ids,
                at=cursor,
                limit=touring_end,
            )
            if meal is None:
                continue
            used_ids.add(meal.item_id)
            item, cursor = _place(
                meal,
                cursor,
                item_type="restaurant",
                slot=beat.slot,
                reason=beat.reason,
                minutes=_meal_stop_minutes(meal),
            )
            schedule.append(item)
            continue
        if beat.kind == "hotel":
            if not hotel:
                continue
            used_ids.add(hotel.item_id)
            star = next(
                (note for note in hotel.why_selected if "star" in note.lower()),
                "",
            )
            start, end, cursor = _clock(cursor, beat.minutes)
            reason = f"{beat.reason} {star}".strip()
            schedule.append(_stay_item(hotel, time=start, end=end, reason=reason))
            continue
        leftover = [card for card in raw_pois if card.item_id not in used_ids]
        sight = next(
            (card for card in leftover if _fits_listing(cursor, card, touring_end)),
            None,
        )
        if sight is None:
            continue
        used_ids.add(sight.item_id)
        item, cursor = _place(
            sight,
            cursor,
            item_type="poi",
            slot=beat.slot,
            reason=beat.reason,
        )
        schedule.append(item)

    if plan.allow_activities and cursor is not None:
        poi_n = sum(1 for item in schedule if item["type"] == "poi")
        cap = 2 if plan.window == "twilight" else 4
        if "relax" in plan.pace.lower():
            cap = min(cap, 3)
        while poi_n < cap:
            leftover = [card for card in raw_pois if card.item_id not in used_ids]
            sight = next(
                (card for card in leftover if _fits_listing(cursor, card, touring_end)),
                None,
            )
            if sight is None:
                break
            used_ids.add(sight.item_id)
            item, cursor = _place(
                sight,
                cursor,
                item_type="poi",
                reason="Time remains after rest, so the arrival day continues nearby — not a long drive.",
            )
            schedule.append(item)
            poi_n += 1
    if hotel and not any(item["type"] == "hotel" for item in schedule):
        schedule.append(
            _stay_item(
                hotel,
                reason="Back to your arrival hotel for the night.",
            )
        )

    names = [item["name"] for item in schedule if item["type"] == "poi"]
    return {
        "day": intent.day,
        "date": intent.date,
        "region": intent.region,
        "theme": intent.theme,
        "summary": _arrival_summary(plan, intent, names),
        "is_arrival_day": True,
        "schedule": schedule,
        "smes": [],
        "transport_notes": arrival_transport_note(plan, intent.region),
    }


def _place_label(key: str) -> str:
    return DISPLAY_NAME.get(key, (key or "").replace("_", " ").title() or "Jordan")


def _transfer_item(
    from_key: str,
    to_key: str,
    cursor: datetime,
    minutes: int,
    *,
    going_home: bool = False,
) -> tuple[dict[str, Any], datetime]:
    start, end, done = _clock(cursor, minutes)
    origin = _place_label(from_key)
    dest = _place_label(to_key)
    name = f"Return to {dest}" if going_home else f"Drive to {dest}"
    reason = (
        "Back to tonight's hotel before dinner."
        if going_home
        else "You woke up in a different place than today's sights."
    )
    return (
        {
            "time": start,
            "end_time": end,
            "slot": "morning" if cursor.hour < 13 else "afternoon",
            "type": "transfer",
            "item_id": f"transfer:{from_key}:{to_key}:{start}",
            "name": name,
            "duration_minutes": minutes,
            "location": f"{origin} → {dest}",
            "coordinates": None,
            "description": f"Travel from {origin} to {dest}.",
            "reason": reason,
            "matched_preferences": [],
            "estimated_cost": "not_available",
            "source": {"dataset": "planning", "record_id": f"transfer:{from_key}:{to_key}"},
            "confidence": "high",
        },
        done,
    )


def _exploring_summary(
    intent: DayIntent,
    schedule: list[dict[str, Any]],
    *,
    transfer_from: str = "",
) -> str:
    pois = [item["name"] for item in schedule if item["type"] == "poi"]
    meals = [item for item in schedule if item["type"] == "restaurant"]
    bits: list[str] = []
    if transfer_from:
        bits.append(f"Morning transfer from {transfer_from} to {intent.region}")
    if pois:
        bits.append(f"visits {', '.join(pois[:3])}")
    if len(meals) >= 3:
        bits.append("with breakfast, lunch, and dinner on the clock")
    elif meals:
        bits.append("with meals on the clock")
    text = ", ".join(bits) if bits else f"A quieter day in {intent.region}"
    return text[0].upper() + text[1:] + "."


def _build_day(
    intent: DayIntent,
    shortlist: DayShortlist | None,
    *,
    include_hotel: bool,
    check_in: bool,
    heat: bool,
    used_ids: set[str],
    airport: str,
    profile: TouristProfile,
    stay_notes: list[str],
    used_meal_names: set[str] | None = None,
    from_key: str = "",
) -> dict[str, Any]:
    if intent.is_arrival_day:
        return _build_arrival_day(
            intent,
            shortlist,
            check_in=check_in and include_hotel,
            airport=airport,
            used_ids=used_ids,
            profile=profile,
            stay_notes=stay_notes,
            heat=heat,
        )
    raw_pois = _pick_outdoor_first(list(shortlist.pois) if shortlist else [], heat)
    meal_used: set[str] = set()
    kitchens = list(shortlist.restaurants) if shortlist else []
    hotels = list(shortlist.hotels) if shortlist else []
    schedule: list[dict[str, Any]] = []
    visit_key = intent.region_key
    overnight_key = intent.overnight_key or intent.region_key
    woke_in = from_key or overnight_key
    inbound = _drive_minutes(woke_in, visit_key) if woke_in != visit_key else 0
    meal_kw = {
        "visit_key": visit_key,
        "overnight_key": overnight_key,
        "also_key": getattr(intent, "paired_key", "") or "",
        "woke_in": woke_in,
        "avoid_names": used_meal_names or set(),
    }
    day_clock = build_exploring_day_clock(profile, intent)
    cursor = day_clock.day_start
    sights = max(intent.sights, 0)
    afternoon_share = 2 if sights >= 4 else (1 if sights >= 2 else 0)
    morning_share = max(sights - afternoon_share, 2 if sights else 0)
    lunch_at = day_clock.lunch_at
    dinner_at = day_clock.dinner_at
    morning_limit = day_clock.morning_sights_end
    going_home = overnight_key != visit_key
    drive_home = _drive_minutes(visit_key, overnight_key) if going_home else 0
    afternoon_limit = min(dinner_at - timedelta(minutes=drive_home), day_clock.day_end)

    meal_kw["day_clock"] = day_clock
    cursor, _ = _ensure_meal(
        kitchens, cursor, "breakfast", meal_used, schedule, **meal_kw
    )
    if inbound:
        item, cursor = _transfer_item(woke_in, visit_key, cursor, inbound)
        schedule.append(item)
    cursor, packed = _pack_sights(
        raw_pois, cursor, morning_limit, morning_share, used_ids, schedule
    )
    cursor = _fill_until(
        raw_pois, cursor, morning_limit, lunch_at, used_ids, schedule,
        reserve=afternoon_share,
    )
    cursor, _ = _ensure_meal(
        kitchens, cursor, "lunch", meal_used, schedule, **meal_kw
    )
    cursor, packed = _pack_sights(
        raw_pois, cursor, afternoon_limit, afternoon_share, used_ids, schedule
    )
    cursor = _fill_until(
        raw_pois, cursor, afternoon_limit, afternoon_limit, used_ids, schedule,
    )
    if going_home and drive_home:
        item, cursor = _transfer_item(visit_key, overnight_key, cursor, drive_home, going_home=True)
        schedule.append(item)
    cursor, _ = _ensure_meal(
        kitchens, cursor, "dinner", meal_used, schedule, **meal_kw
    )

    if include_hotel and check_in and hotels:
        poi_anchor = next(
            (card for card in raw_pois if card.item_id in used_ids and card.latitude is not None),
            None,
        )
        hotel = pick_stay_hotel(
            hotels,
            intent.overnight_key or intent.region_key,
            near_lat=poi_anchor.latitude if poi_anchor else None,
            near_lon=poi_anchor.longitude if poi_anchor else None,
            profile=profile,
        )
        if hotel:
            used_ids.add(hotel.item_id)
            _note_stay_gap(hotel, intent, profile, stay_notes)
            schedule.append(
                _stay_item(
                    hotel,
                    reason=_stay_reason(hotel, intent),
                )
            )

    summary = _exploring_summary(
        intent,
        schedule,
        transfer_from=_place_label(woke_in) if inbound else "",
    )
    return {
        "day": intent.day,
        "date": intent.date,
        "region": intent.region,
        "theme": intent.theme,
        "summary": summary,
        "is_arrival_day": False,
        "schedule": schedule,
        "smes": [],
        "transport_notes": _transport_note(intent, check_in),
    }


def _build_budget(
    profile: TouristProfile,
    days: list[dict[str, Any]],
    smes: list[dict[str, Any]],
) -> dict[str, Any]:
    stays: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    nights_left = profile.nights
    meal_total = 0.0
    meal_n = 0
    meal_missing = 0
    ticket_total = 0.0
    ticket_n = 0
    ticket_missing = 0

    for day in days:
        hotel_item = next((item for item in day["schedule"] if item.get("type") == "hotel"), None)
        if hotel_item:
            if current:
                stays.append(current)
            current = {
                "name": hotel_item["name"],
                "nights": 0,
                "price": _amount(hotel_item.get("estimated_cost")),
            }
        if current and nights_left > 0:
            current["nights"] += 1
            nights_left -= 1
        for item in day["schedule"]:
            amount = _amount(item.get("estimated_cost"))
            if item.get("type") == "restaurant":
                if amount is None:
                    meal_missing += 1
                else:
                    meal_total += amount * profile.total_travelers
                    meal_n += 1
            elif item.get("type") == "poi":
                if amount is None:
                    ticket_missing += 1
                else:
                    ticket_total += amount * profile.total_travelers
                    ticket_n += 1
    if current:
        stays.append(current)

    lodging_total = 0.0
    lodging_nights = 0
    lodging_notes: list[str] = []
    for stay in stays:
        if stay["price"] is not None:
            lodging_total += stay["price"] * stay["nights"]
            lodging_nights += stay["nights"]
            lodging_notes.append(f"{stay['name']}: {stay['price']:g} JOD × {stay['nights']} night(s)")
        else:
            lodging_notes.append(f"{stay['name']}: no listed night rate")

    items: list[dict[str, str]] = []

    def add(category: str, total: float, notes: str, known: int) -> None:
        if known:
            items.append(
                {
                    "category": category,
                    "estimated_cost": f"{round(total, 1):g} JOD",
                    "notes": notes,
                    "confidence": "medium",
                }
            )
        else:
            items.append(
                {
                    "category": category,
                    "estimated_cost": "not_available",
                    "notes": notes or "No listed price in the catalog.",
                    "confidence": "low",
                }
            )

    add("Stays", lodging_total, "; ".join(lodging_notes) or "No hotel nights on the plan.", lodging_nights)
    meal_note = f"{meal_n} listed meal(s) × {profile.total_travelers} traveler(s)."
    if meal_missing:
        meal_note += f" {meal_missing} meal(s) have no listed price."
    add("Meals on the plan", meal_total, meal_note, meal_n)
    ticket_note = f"{ticket_n} listed site(s) × {profile.total_travelers} traveler(s)."
    if ticket_missing:
        ticket_note += f" {ticket_missing} site(s) have no listed entry fee."
    add("Entry tickets", ticket_total, ticket_note, ticket_n)

    sme_total = 0.0
    sme_known = 0
    for sme in smes:
        price = sme.get("min_price")
        label = sme.get("role") or sme.get("name") or "Local host"
        if price is None:
            items.append(
                {
                    "category": str(label),
                    "estimated_cost": "not_available",
                    "notes": "No listed rate in the SME directory.",
                    "confidence": "low",
                }
            )
            continue
        model = str(sme.get("pricing_model") or "").lower()
        days_n = profile.duration_days
        if "daily" in model:
            cost = float(price) * days_n
            notes = f"Listed daily rate {float(price):g} JOD × {days_n} days"
        else:
            cost = float(price)
            notes = f"Listed from {float(price):g} JOD"
        high = sme.get("max_price")
        if high not in (None, ""):
            notes += f" (up to {float(high):g} JOD listed)"
        sme_total += cost
        sme_known += 1
        items.append(
            {
                "category": str(label),
                "estimated_cost": f"{round(cost, 1):g} JOD",
                "notes": notes,
                "confidence": "medium",
            }
        )

    parts = []
    if lodging_nights:
        parts.append(lodging_total)
    if meal_n:
        parts.append(meal_total)
    if ticket_n:
        parts.append(ticket_total)
    if sme_known:
        parts.append(sme_total)
    estimated = sum(parts) if parts else None
    if estimated is not None:
        leftover = profile.total_budget - estimated
        items.append(
            {
                "category": "Left vs your ceiling",
                "estimated_cost": f"{round(leftover, 1):g} JOD",
                "notes": (
                    f"Your ceiling is {profile.total_budget:g} JOD. "
                    f"Listed pieces add up to {round(estimated, 1):g} JOD."
                ),
                "confidence": "medium",
            }
        )

    return {
        "currency": "JOD",
        "traveler_budget": profile.total_budget,
        "estimated_total": f"{round(estimated, 1):g} JOD" if estimated is not None else "not_available",
        "band": budget_band(profile.total_budget, profile.duration_days),
        "items": items,
        "disclaimer": (
            "Amounts come from catalog listings. This is a planning estimate, not a final invoice. "
            "Missing prices stay unknown — we do not invent them."
        ),
    }


def build_locked_package(
    profile: TouristProfile,
    context: PlanningContext,
    knowledge: RetrievedKnowledge,
    sme_matches: list[SMEMatch],
) -> TourismPackage:
    short_by_day = {item.day: item for item in knowledge.day_shortlists}
    team = list(sme_matches[:2])
    used_smes = [sme_payload(match) for match in team]
    days: list[dict[str, Any]] = []
    scheduled_names: list[str] = []
    scheduled_regions: list[str] = []
    sources: list[dict[str, str]] = []
    used_ids: set[str] = set()
    used_meal_names: set[str] = set()
    overnight_key = ""
    stay_notes: list[str] = []

    for index, intent in enumerate(context.day_intents):
        include_hotel = index < profile.nights
        check_in = include_hotel and (intent.overnight_key or intent.region_key) != overnight_key
        day = _build_day(
            intent,
            short_by_day.get(intent.day),
            include_hotel=include_hotel,
            check_in=check_in,
            heat=context.climate.heat_risk == "high",
            used_ids=used_ids,
            airport=profile.arrival_airport,
            profile=profile,
            stay_notes=stay_notes,
            used_meal_names=used_meal_names,
            from_key=overnight_key,
        )
        if any(item.get("type") == "hotel" for item in day["schedule"]):
            overnight_key = intent.overnight_key or intent.region_key
        elif not intent.is_arrival_day:
            overnight_key = intent.overnight_key or intent.region_key
        used_meal_names.update(
            venue_name_key(str(item.get("name") or ""))
            for item in day["schedule"]
            if item.get("type") == "restaurant"
        )
        days.append(day)
        for item in day["schedule"]:
            scheduled_names.append(item["name"])
            scheduled_regions.append(item.get("location") or intent.region)
            if item.get("source"):
                sources.append(item["source"])
    for sme in used_smes:
        if sme.get("source"):
            sources.append(sme["source"])

    constraint = evaluate_constraints(profile, scheduled_names, scheduled_regions)
    highlights = [item["name"] for day in days for item in day["schedule"] if item["type"] == "poi"][:6]
    why_smes = []
    for sme in used_smes:
        if sme.get("reason"):
            why_smes.append(f"{sme['name']}: {sme['reason']}")
        elif sme.get("known_for"):
            why_smes.append(f"{sme['name']}: {sme['known_for'][0]}")
    decisions = [item.model_dump(mode="json") for item in context.decisions]
    title = (
        " · ".join(
            dict.fromkeys(
                intent.region for intent in context.day_intents if not intent.is_arrival_day
            )
        )
        or "Jordan journey"
    )
    route_label = _route_phrase(context.day_intents)
    payload = {
        "package_id": f"pkg-{uuid4().hex[:12]}",
        "status": "complete" if constraint["status"] == "satisfied" else "partial",
        "welcome_message": (
            f"Land in {context.day_intents[0].region if context.day_intents else 'Jordan'}, "
            f"then {profile.exploration_days} exploring "
            f"{'day' if profile.exploration_days == 1 else 'days'} through {route_label}."
        ),
        "trip_title": title,
        "trip": {
            "title": title,
            "summary": (
                f"Arrival, then {route_label}. "
                f"{context.climate.outdoor_guidance}"
            ),
            "start_date": profile.start_date.isoformat(),
            "end_date": profile.end_date.isoformat(),
            "duration_days": profile.duration_days,
            "nights": profile.nights,
            "regions": list(dict.fromkeys(intent.region for intent in context.day_intents)),
            "arrival_airport": profile.arrival_airport,
            "language": profile.preferred_language,
        },
        "planning": {
            "strategy": tourist_planning_reason(context),
            "constraints": {
                "must_visit": profile.must_visit,
                "places_to_avoid": profile.places_to_avoid,
            },
            "constraint_status": constraint,
            "assumptions": context.assumptions,
            "climate": context.climate.model_dump(mode="json"),
            "weather_status": context.weather_status,
            "decisions": decisions,
        },
        "days": days,
        "budget": _build_budget(profile, days, used_smes),
        "sme_value": {
            "headline": "Your guide and operator for this journey",
            "summary": (
                "One local guide and one tour operator for the whole trip — "
                "not a new face every day."
            ),
            "recommended": used_smes,
        },
        "sources": sources,
        "warnings": [
            {"code": "note", "message": w, "severity": "info"}
            for w in [*knowledge.warnings, *stay_notes]
        ],
        "explanations": {
            "trip_planning_reason": tourist_planning_reason(context),
            "highlights": highlights,
            "why_smes": why_smes[:6],
            "context_benefits": planner_notes(context),
        },
    }
    return TourismPackage.model_validate(payload)


def overlay_narrative(skeleton: TourismPackage, llm_package: TourismPackage) -> TourismPackage:
    """Keep locked IDs. Take only titles, summaries, and matching-item wording from the model."""
    data = skeleton.model_dump(mode="python")
    if llm_package.trip_title:
        data["trip_title"] = llm_package.trip_title
        data["trip"]["title"] = llm_package.trip_title
    llm_days = {day.day: day for day in llm_package.days}
    for day in data["days"]:
        llm_day = llm_days.get(day["day"])
        if llm_day is None:
            continue
        is_arrival = bool(day.get("is_arrival_day")) or str(day.get("theme") or "").lower().startswith("arrival")
        if llm_day.theme and not is_arrival:
            day["theme"] = llm_day.theme
        by_id = {item.item_id: item for item in llm_day.schedule if item.item_id}
        for item in day["schedule"]:
            extra = by_id.get(item["item_id"])
            if extra is None:
                continue
            if extra.description and not is_arrival:
                item["description"] = extra.description
            if extra.reason and item.get("type") != "hotel" and not is_arrival:
                item["reason"] = extra.reason
            # time, end_time, duration_minutes, estimated_cost stay from the catalog.
    return TourismPackage.model_validate(data)
