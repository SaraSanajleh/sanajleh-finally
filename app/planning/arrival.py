"""Arrival day is its own phase: land, eat, rest, then only what the clock still allows."""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel


class ArrivalPlan(BaseModel):
    time: str
    hour: int
    minute: int
    window: str
    pace: str = "Balanced"
    airport: str = "AMM"
    transfer_minutes: int = 45
    rest_hours: int = 3
    allow_activities: bool = False
    activity_count: int = 0
    meal_first: bool = True
    meal_label: str = "lunch"
    earliest_activity_hour: int = 10
    latest_activity_hour: int = 19


class ArrivalBeat(BaseModel):
    kind: str
    start: datetime
    minutes: int
    slot: str
    reason: str
    meal_label: str = ""


def parse_hhmm(value: str | None) -> tuple[int, int]:
    text = (value or "14:00").strip()
    try:
        hour_s, minute_s = text.split(":", 1)
        hour = max(0, min(23, int(hour_s)))
        minute = max(0, min(59, int(minute_s[:2])))
        return hour, minute
    except (TypeError, ValueError):
        return 14, 0


def transfer_minutes_for(airport: str | None) -> int:
    if (airport or "AMM").upper() == "AQJ":
        return 20
    return 45


def classify_arrival_window(hour: int, minute: int = 0) -> str:
    """Available time, not a sightseeing label.

    overnight  00:00–07:00  kitchens closed; sleep first
    daytime    07:00–15:00  food, 3–5h rest, then a mini-itinerary if light remains
    twilight   15:00–20:00  food and rest; activities only if time remains before night
    night      20:00–24:00  food, hotel, sleep — no sightseeing
    """
    stamp = hour * 60 + minute
    if stamp < 7 * 60:
        return "overnight"
    if stamp < 15 * 60:
        return "daytime"
    if stamp < 20 * 60:
        return "twilight"
    return "night"


def _meal_label_for(window: str, hour: int) -> str:
    if window == "overnight":
        return "breakfast"
    if 7 <= hour < 11:
        return "breakfast"
    if 11 <= hour < 16:
        return "lunch"
    return "dinner"


def _rest_hours(window: str, pace: str, hour: int = 8) -> int:
    pace_key = (pace or "").lower()
    if window == "overnight":
        base = 6
    elif window == "daytime":
        # 3–5 hours, shorter when the landing is already late morning.
        base = 3 if hour >= 10 else 4
    elif window == "twilight":
        base = 2
    else:
        return 0
    if "relax" in pace_key:
        return min(5, base + 1) if window == "daytime" else min(8, base + 1)
    if "fast" in pace_key:
        return max(3, base - 1) if window == "daytime" else max(1, base - 1)
    return base


def _activity_cap(window: str, pace: str) -> int:
    if window == "night":
        return 0
    if window == "twilight":
        return 2
    cap = 4
    if "relax" in (pace or "").lower():
        cap = 3
    return cap


def plan_arrival(
    arrival_time: str | None,
    pace: str = "Balanced",
    airport: str | None = "AMM",
) -> ArrivalPlan:
    hour, minute = parse_hhmm(arrival_time)
    window = classify_arrival_window(hour, minute)
    transfer = transfer_minutes_for(airport)
    rest = _rest_hours(window, pace or "Balanced", hour)
    cap = _activity_cap(window, pace or "Balanced")
    latest = 21 if window == "twilight" else 19
    meal_first = window not in {"overnight"}
    draft = ArrivalPlan(
        time=f"{hour:02d}:{minute:02d}",
        hour=hour,
        minute=minute,
        window=window,
        pace=pace or "Balanced",
        airport=(airport or "AMM").upper(),
        transfer_minutes=transfer,
        rest_hours=rest,
        allow_activities=cap > 0,
        activity_count=cap,
        meal_first=meal_first,
        meal_label=_meal_label_for(window, hour),
        earliest_activity_hour=10 if window == "overnight" else 8,
        latest_activity_hour=latest,
    )
    ready = _ready_time(draft)
    touring_end = datetime(2000, 1, 1, latest, 0)
    remaining = _minutes_left(ready, touring_end)
    count = 0 if remaining < 60 else min(cap, max(2 if remaining >= 120 else 1, remaining // 60))
    if window == "night":
        count = 0
    if window == "twilight" and remaining < 90:
        count = 0
    if remaining >= 120 and count < 2:
        count = min(cap, 2)
    return draft.model_copy(
        update={
            "activity_count": count,
            "allow_activities": count > 0,
        }
    )


def _meal_for_hour(hour: int) -> str:
    if 7 <= hour < 11:
        return "breakfast"
    if 11 <= hour < 16:
        return "lunch"
    if 17 <= hour < 22:
        return "dinner"
    return ""


def _hotel_reason(plan: ArrivalPlan) -> str:
    if plan.window == "overnight":
        return (
            "You land before dawn. Go to your hotel and sleep properly — "
            "this is rest, not a visit. The day starts after you wake."
        )
    if plan.window == "daytime":
        return "Check in, eat nearby, and rest 3–5 hours. Remaining light is for a short same-city plan."
    if plan.window == "twilight":
        return "Check in and rest first. Add a nearby stop only if enough evening is left."
    return "Check in and sleep. Sightseeing starts tomorrow."


def _meal_reason_for(label: str, *, before_rest: bool) -> str:
    if label == "breakfast" and not before_rest:
        return "Breakfast after rest — kitchens were closed when you landed."
    if label == "breakfast":
        return "About an hour for breakfast after the airport transfer, then rest."
    if label == "lunch" and not before_rest:
        return "A meal after rest, at a normal hour."
    if label == "lunch":
        return "About an hour for lunch after landing, then rest at the hotel."
    if label == "dinner" and before_rest:
        return "Dinner near the hotel. Nothing more tonight."
    return "A simple dinner if the kitchen is still open, then sleep."


def _rest_until(plan: ArrivalPlan, cursor: datetime) -> datetime:
    if plan.window == "overnight":
        target_hour = 11 if "relax" in plan.pace.lower() else 10
        target = cursor.replace(hour=target_hour, minute=30, second=0, microsecond=0)
        if target.day != cursor.day or target <= cursor:
            target = cursor + timedelta(hours=max(plan.rest_hours, 5))
        minimum = cursor + timedelta(hours=max(plan.rest_hours, 5))
        return max(target, minimum)
    if plan.window == "night":
        end = cursor.replace(hour=7, minute=0, second=0, microsecond=0) + timedelta(days=1)
        if end <= cursor:
            end = cursor + timedelta(hours=8)
        return end
    return cursor + timedelta(hours=max(plan.rest_hours, 2 if plan.window == "twilight" else 3))


def _minutes_left(cursor: datetime, end: datetime) -> int:
    if cursor.date() != end.date() or cursor >= end:
        return 0
    return int((end - cursor).total_seconds() // 60)


def _ready_time(plan: ArrivalPlan) -> datetime:
    land = datetime(2000, 1, 1, plan.hour, plan.minute)
    cursor = land + timedelta(minutes=plan.transfer_minutes)
    if plan.meal_first and _meal_for_hour(cursor.hour):
        cursor = cursor + timedelta(minutes=60)
    cursor = _rest_until(plan, cursor)
    return cursor


def arrival_beats(plan: ArrivalPlan) -> list[ArrivalBeat]:
    """Food, rest, then a mini-itinerary only for the time that is actually left."""
    land = datetime(2000, 1, 1, plan.hour, plan.minute)
    cursor = land + timedelta(minutes=plan.transfer_minutes)
    beats: list[ArrivalBeat] = []
    last_meal = ""

    def add(kind: str, minutes: int, slot: str, reason: str, meal_label: str = "") -> None:
        nonlocal cursor
        beats.append(
            ArrivalBeat(
                kind=kind,
                start=cursor,
                minutes=max(minutes, 20),
                slot=slot,
                reason=reason,
                meal_label=meal_label,
            )
        )
        cursor = cursor + timedelta(minutes=max(minutes, 20))

    if plan.meal_first:
        first = _meal_for_hour(cursor.hour)
        if first:
            add("meal", 60, first, _meal_reason_for(first, before_rest=True), first)
            last_meal = first

    rest_end = _rest_until(plan, cursor)
    rest_minutes = max(int((rest_end - cursor).total_seconds() // 60), 30)
    add("hotel", rest_minutes, "rest", _hotel_reason(plan))

    if cursor.day != land.day:
        return beats

    after = _meal_for_hour(cursor.hour)
    if after and after != last_meal:
        add("meal", 60, after, _meal_reason_for(after, before_rest=False), after)
        last_meal = after

    if cursor.hour < plan.earliest_activity_hour and cursor.day == land.day:
        snap = cursor.replace(hour=plan.earliest_activity_hour, minute=0, second=0, microsecond=0)
        if snap > cursor:
            cursor = snap

    touring_end = land.replace(hour=plan.latest_activity_hour, minute=0, second=0, microsecond=0)
    poi_count = 0
    while plan.activity_count > 0 and poi_count < plan.activity_count:
        left = _minutes_left(cursor, touring_end)
        if left < 60:
            break
        lunch_due = (
            last_meal == "breakfast"
            and 12 <= cursor.hour < 16
            and left >= 90
        )
        if lunch_due:
            add(
                "meal",
                60,
                "lunch",
                "Lunch nearby. You still have time left in the same city.",
                "lunch",
            )
            last_meal = "lunch"
            continue
        duration = min(75, max(45, left - 15))
        if duration < 45:
            break
        slot = "morning" if cursor.hour < 12 else "afternoon"
        add(
            "poi",
            duration,
            slot,
            "Time remains after rest, so the arrival day continues nearby — not a long drive.",
        )
        poi_count += 1
        if _minutes_left(cursor, touring_end) >= 90:
            cursor = cursor + timedelta(minutes=15)

    return beats


def arrival_transport_note(plan: ArrivalPlan, city: str) -> str:
    airport = "Queen Alia" if plan.airport == "AMM" else "King Hussein / Aqaba"
    return (
        f"You land at {plan.time}. The drive from {airport} to {city or 'the hotel'} "
        f"is about {plan.transfer_minutes} minutes. Times below start after that transfer."
    )
