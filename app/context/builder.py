"""Build a deterministic PlanningContext from the tourist profile."""

from __future__ import annotations

from app.config.settings import AppSettings, get_app_settings
from datetime import timedelta

from app.context.models import (
    BudgetFrame,
    ClimateWindow,
    ContextDecision,
    DayIntent,
    GeographicFrame,
    PaceFrame,
    PlanningContext,
    TravelerFrame,
)
from app.context.weather import fetch_weather
from app.planning.arrival import plan_arrival
from app.planning.profile import TouristProfile, budget_band, pace_slots
from app.planning.route import HALF_LABEL, plan_day_route

INTEREST_PHRASE = {
    "history": "history",
    "nature": "nature",
    "food": "food",
    "culture": "culture",
    "adventure": "adventure",
    "shopping": "shopping",
    "photography": "photography",
    "desert": "the desert",
    "beaches": "the coast",
    "art": "art",
    "wellness": "wellness",
    "hiking": "hiking",
    "camping": "camping",
    "local_experiences": "local experiences",
    "festivals": "festivals",
    "archaeology": "archaeology",
    "religious_sites": "religious sites",
    "cycling": "cycling",
    "scenic_views": "views",
    "luxury": "comfort",
    "local_events": "local events",
    "eco_tourism": "nature reserves",
    "wildlife": "wildlife",
    "museums": "museums",
}


def interest_phrase(interests: list[str]) -> str:
    labels = [INTEREST_PHRASE.get(item, item.replace("_", " ")) for item in interests[:3] if item]
    if not labels:
        return "what you asked for"
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return f"{labels[0]}, {labels[1]}, and {labels[2]}"


def climate_for_month(month: int) -> ClimateWindow:
    if month in (6, 7, 8, 9):
        return ClimateWindow(
            month=month,
            season="hot_dry_summer",
            typical_pattern="High daytime heat, especially in the Jordan Valley and desert.",
            outdoor_guidance="Walk outdoors in the morning. Keep the afternoon for shade, meals, or indoor visits.",
            heat_risk="high",
        )
    if month in (12, 1, 2):
        return ClimateWindow(
            month=month,
            season="cool_winter",
            typical_pattern="Cooler days, possible rain in the highlands; milder in Aqaba and the Dead Sea.",
            outdoor_guidance="Outdoor sites are still fine. Pack layers, and keep an indoor backup if rain looks likely.",
            heat_risk="low",
        )
    if month in (3, 4, 5):
        return ClimateWindow(
            month=month,
            season="mild_spring",
            typical_pattern="Generally comfortable touring weather across most regions.",
            outdoor_guidance="A good window for walking, nature, and archaeological sites.",
            heat_risk="moderate",
        )
    return ClimateWindow(
        month=month,
        season="mild_autumn",
        typical_pattern="Warm days easing from summer heat; strong touring season.",
            outdoor_guidance="Mornings and afternoons outdoors are usually comfortable.",
        heat_risk="moderate",
    )


def _budget_guidance(band: str) -> str:
    return {
        "value": "Prefer modest dining and midscale stays. Do not invent prices.",
        "moderate": "Balance comfort and value. Use dataset prices only when present.",
        "comfort": "Comfort-oriented stays and dining when listed places exist.",
        "premium": "Prefer higher-rated stays when they exist. Never invent luxury venues.",
    }.get(band, "Use listed prices only. Unknown prices stay not_available.")


def _budget_traveler_effect(band: str) -> str:
    return {
        "value": "Stays and meals stay modest. We only show a price when a listing has one.",
        "moderate": "A mix of comfortable and good-value stays and meals, with listed prices only.",
        "comfort": "We lean toward more comfortable stays and dining when those places exist.",
        "premium": "We prefer higher-rated stays when they exist. We never invent luxury places.",
    }.get(band, "Prices appear only when a listing actually has them.")


def _route_phrase(stops: list) -> str:
    """Petra, Petra, Wadi Rum → 'Petra (2 days), then Wadi Rum'."""
    chunks: list[tuple[str, int]] = []
    for stop in stops:
        if getattr(stop, "is_arrival_day", False):
            continue
        region = getattr(stop, "region", "") or ""
        if not region:
            continue
        if chunks and chunks[-1][0] == region:
            chunks[-1] = (region, chunks[-1][1] + 1)
        else:
            chunks.append((region, 1))
    parts = [name if count == 1 else f"{name} ({count} days)" for name, count in chunks]
    if not parts:
        return "Jordan"
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]}, then {parts[1]}"
    return ", ".join(parts[:-1]) + f", then {parts[-1]}"


def tourist_planning_reason(context: PlanningContext) -> str:
    """Two or three sentences a desk planner would write on the file."""
    arrival = next((item for item in context.day_intents if item.is_arrival_day), None)
    city = (arrival.region if arrival else "") or "Amman"
    stamp = (arrival.arrival_time if arrival else "") or ""
    route = _route_phrase(context.day_intents)
    if stamp:
        first = (
            f"You land at {stamp}, so arrival night stays in {city} — "
            "hotel, a meal, rest. The touring days start the next morning."
        )
    else:
        first = (
            f"Arrival night stays in {city}. "
            "The touring days start the next morning."
        )
    musts = [item for item in context.geographic.must_visit if item]
    if musts:
        named = ", ".join(musts[:3])
        second = (
            f"I put {named} on the calendar first, then kept the rest of the days on {route}."
            if route and route != "Jordan"
            else f"I put {named} on the calendar first."
        )
    elif route and route != "Jordan":
        second = f"After that the days stay on a short loop: {route}."
    else:
        second = ""
    third = ""
    if context.climate.heat_risk == "high":
        third = "It's a hot month, so the outdoor sites go before midday."
    return " ".join(part for part in (first, second, third) if part)


def planner_notes(context: PlanningContext) -> list[str]:
    """Unused on the traveler card — keep empty so old title:effect lists cannot leak."""
    _ = context
    return []


async def build_planning_context(
    profile: TouristProfile,
    settings: AppSettings | None = None,
    inferred_dests: list[tuple[str, str, bool]] | None = None,
) -> PlanningContext:
    settings = settings or get_app_settings()
    slots = pace_slots(profile.trip_pace)
    band = budget_band(profile.total_budget, profile.duration_days)
    per_day = profile.total_budget / max(profile.duration_days, 1)
    climate = climate_for_month(profile.start_date.month)
    weather, weather_status = await fetch_weather(
        region_keys=profile.region_keys,
        start=profile.start_date,
        days=profile.duration_days,
        enabled=settings.weather_enabled,
        timeout=settings.weather_timeout_seconds,
    )

    rules = [
        "Never invent POIs, hotels, restaurants, SMEs, prices, hours, or coordinates.",
        "Use only retrieved catalog IDs. If a needed item is missing, leave it unknown and warn.",
        "Must-visit destinations are hard constraints unless impossible.",
        "Honor places_to_avoid as a hard exclusion.",
        "Keep each day geographically coherent.",
        "Day 1 is the arrival phase, not an exploration day. Wizard duration is the exploring days after arrival.",
        f"Target about {slots['sights']} sights and {slots['meals']} meals per exploring day for a {profile.trip_pace} pace.",
        "Recommend at most one tour guide and one tour operator for the whole package, not per day.",
        "Tourist relevance always outranks commercial promotion.",
    ]
    if profile.has_children:
        rules.append("Prefer family-suitable catalog items when audience data supports it.")
    if profile.limited_mobility:
        rules.append("Prefer accessible or lower-walking catalog items when accessibility data exists.")
    if climate.heat_risk == "high":
        rules.append("Avoid stacking outdoor sites in peak afternoon heat.")
    if weather_status != "ok":
        rules.append("Weather is unknown — do not claim live conditions.")

    assumptions: list[str] = []
    unknowns: list[str] = []
    if weather_status != "ok":
        unknowns.append("live_weather")
        assumptions.append("Seasonal climate guidance is used because live weather is unavailable.")
    assumptions.append("Travel times between cities are estimated qualitatively, not as exact minutes, unless evidence exists.")
    assumptions.append("Opening hours are used only when present on the catalog record.")

    route = plan_day_route(profile, inferred_dests=inferred_dests)
    arrival = plan_arrival(profile.arrival_time, profile.trip_pace, profile.arrival_airport)
    decisions = _context_decisions(
        profile, climate, weather, weather_status, band, slots, route, arrival, inferred_dests
    )
    day_intents = [
        DayIntent(
            day=stop.day,
            date=(profile.start_date + timedelta(days=stop.day - 1)).isoformat(),
            region=stop.region,
            region_key=stop.region_key,
            theme=_day_theme(stop.region, profile, stop.stay_index, stop.is_arrival_day),
            is_must_visit=stop.is_must_visit,
            stay_index=stop.stay_index,
            outdoor_window="morning" if climate.heat_risk == "high" else "flexible",
            indoor_window="afternoon" if climate.heat_risk == "high" else "flexible",
            sights=arrival.activity_count if stop.is_arrival_day else slots["sights"],
            meals=1 if stop.is_arrival_day else slots["meals"],
            heat_note=climate.outdoor_guidance if climate.heat_risk == "high" else "",
            overnight_key=stop.overnight_key,
            overnight_region=stop.overnight_region,
            is_arrival_day=stop.is_arrival_day,
            stay_style=stop.stay_style,
            rest_hours=arrival.rest_hours if stop.is_arrival_day else 0,
            allow_arrival_activities=arrival.allow_activities if stop.is_arrival_day else True,
            arrival_time=arrival.time if stop.is_arrival_day else "",
            paired_key=getattr(stop, "paired_key", "") or "",
        )
        for stop in route
    ]

    return PlanningContext(
        trip_window={
            "start_date": profile.start_date.isoformat(),
            "end_date": profile.end_date.isoformat(),
            "duration_days": profile.duration_days,
            "exploration_days": profile.exploration_days,
            "nights": profile.nights,
            "arrival_airport": profile.arrival_airport,
            "arrival_time": profile.arrival_time,
            "language": profile.preferred_language,
        },
        geographic=GeographicFrame(
            arrival_airport=profile.arrival_airport,
            preferred_regions=profile.preferred_regions,
            region_keys=profile.region_keys,
            must_visit=profile.must_visit,
            places_to_avoid=profile.places_to_avoid,
        ),
        traveler=TravelerFrame(
            group_type=profile.group_type,
            adults=profile.adults,
            children=profile.children,
            children_ages=profile.children_ages,
            seniors=profile.seniors,
            total_travelers=profile.total_travelers,
            accessibility_needs=profile.accessibility_needs,
            limited_mobility=profile.limited_mobility,
            family_mode=profile.has_children or profile.group_type == "family",
        ),
        pace=PaceFrame(
            trip_pace=profile.trip_pace,
            activity_level=profile.activity_level,
            sights_per_day=slots["sights"],
            meals_per_day=slots["meals"],
            max_schedule_items=slots["max_schedule"],
        ),
        budget=BudgetFrame(
            total=profile.total_budget,
            band=band,
            per_day=round(per_day, 2),
            guidance=_budget_guidance(band),
        ),
        climate=climate,
        weather=weather,
        weather_status=weather_status,
        decision_rules=rules,
        assumptions=assumptions,
        unknowns=unknowns,
        decisions=decisions,
        day_intents=day_intents,
    )


def _day_theme(region: str, profile: TouristProfile, stay_index: int, is_arrival: bool = False) -> str:
    if is_arrival:
        return f"Arrival in {region}"
    if stay_index == 0:
        return region
    return f"More time in {region}"


def _context_decisions(
    profile: TouristProfile,
    climate: ClimateWindow,
    weather: list,
    weather_status: str,
    band: str,
    slots: dict[str, int],
    route: list,
    arrival,
    inferred_dests: list | None = None,
) -> list[ContextDecision]:
    decisions: list[ContextDecision] = []
    route_label = _route_phrase(route)
    decisions.append(
        ContextDecision(
            code="day_route",
            title="Each exploring day stays in one area",
            why="Mixing far-apart cities in one day makes the trip exhausting.",
            effect=f"After arrival, the days run {route_label}." if route_label != "Jordan" else "Each exploring day stays in one area.",
        )
    )
    if inferred_dests and not profile.preferred_regions and not profile.must_visit:
        interests = interest_phrase(profile.interests)
        decisions.append(
            ContextDecision(
                code="open_explore",
                title="A route from what you like",
                why=f"No cities were named, so the days follow the places that matched {interests}.",
                effect=f"Those retrieved areas become the route: {route_label}.",
            )
        )
    dropped = next((stop.dropped_half for stop in route if getattr(stop, "dropped_half", "")), "")
    focus = next((stop.focus_half for stop in route if getattr(stop, "focus_half", "")), "")
    if dropped:
        kept = HALF_LABEL.get(focus, focus.replace("_", " "))
        decisions.append(
            ContextDecision(
                code="one_half",
                title="This trip stays in one part of Jordan",
                why=f"{profile.exploration_days} exploring days is too short for both the north and the south.",
                effect=f"So this journey focuses on the {kept}, and those places get proper time.",
            )
        )
    arrival_city = route[0].overnight_region if route else "Amman"
    decisions.append(
        ContextDecision(
            code="arrival_stay",
            title="Night one is near the airport",
            why=f"You land at {profile.arrival_airport} at {arrival.time}.",
            effect=f"Sleep in {arrival_city} on arrival night. The exploring days start the next morning.",
        )
    )
    airport = (profile.arrival_airport or "AMM").upper()
    if airport == "AQJ" and focus == "north_center":
        decisions.append(
            ContextDecision(
                code="arrival_relocate",
                title="You land in the south, then move north",
                why="King Hussein / Aqaba is the arrival airport, but the trip is for North or Central Jordan.",
                effect="Sleep in Aqaba on night one, then relocate before the main exploring days.",
            )
        )
    elif airport == "AMM" and focus == "south":
        decisions.append(
            ContextDecision(
                code="arrival_relocate",
                title="Amman for the first night, then south",
                why="You land at Queen Alia, and the exploring days are in Southern Jordan.",
                effect="Stay in Amman on arrival night, then travel south the next day.",
            )
        )
    if arrival.window == "overnight":
        decisions.append(
            ContextDecision(
                code="arrival_pace",
                title="Sleep first — you still have a day",
                why=f"You land at {arrival.time}, before the city is awake.",
                effect="Go to the hotel and rest properly. After breakfast, nearby visits fill the rest of the arrival day.",
            )
        )
    elif arrival.window == "night":
        decisions.append(
            ContextDecision(
                code="arrival_pace",
                title="A quiet first night",
                why=f"You land at {arrival.time}.",
                effect="Transfer, a simple dinner if kitchens are open, then sleep. Exploring starts tomorrow.",
            )
        )
    elif arrival.window == "twilight":
        decisions.append(
            ContextDecision(
                code="arrival_pace",
                title="Settle in this evening",
                why=f"You land at {arrival.time}.",
                effect="Food and rest first. A nearby stop only if enough evening remains, then back to the hotel.",
            )
        )
    elif arrival.allow_activities:
        decisions.append(
            ContextDecision(
                code="arrival_pace",
                title="Arrive, rest, then a short same-city plan",
                why=f"You arrive at {arrival.time}.",
                effect="About an hour for food, several hours of rest, then whatever daylight is left nearby — not a long drive.",
            )
        )
    else:
        decisions.append(
            ContextDecision(
                code="arrival_pace",
                title="Ease in after landing",
                why=f"You arrive at {arrival.time}.",
                effect="Transfer, eat, rest at the hotel. Exploring starts the next day.",
            )
        )
    if any(getattr(stop, "stay_style", "") == "day_trip" for stop in route):
        hub = next(
            (stop.overnight_region for stop in route if getattr(stop, "stay_style", "") == "day_trip"),
            arrival_city,
        )
        decisions.append(
            ContextDecision(
                code="day_trips",
                title="Day trips from one hotel",
                why="These places are close enough to visit and return the same day.",
                effect=f"You keep the same hotel in {hub} and come back there to sleep.",
            )
        )
    if any(
        getattr(stop, "overnight_key", "") not in {"", getattr(route[0], "overnight_key", "")}
        for stop in route[1:]
    ):
        decisions.append(
            ContextDecision(
                code="hotel_move",
                title="Then you move closer to the places you came for",
                why="Sleeping in the same city you visit beats a long commute every morning.",
                effect="After the arrival night, nearby days share one hotel. You only move when the next area is too far for a day trip.",
            )
        )
    if profile.must_visit:
        extra = (
            " Then the remaining days go to the destinations you asked to explore."
            if profile.preferred_regions
            else ""
        )
        decisions.append(
            ContextDecision(
                code="must_visit",
                title="Your must-see places get proper time",
                why=", ".join(profile.must_visit) + " were marked as required.",
                effect="Those places get up to two exploring days first." + extra,
            )
        )
    if climate.heat_risk == "high":
        decisions.append(
            ContextDecision(
                code="heat",
                title="Mornings for the outdoors",
                why=climate.typical_pattern,
                effect="Walk heritage and nature in the morning. Save museums, meals, and shade for the afternoon.",
            )
        )
    elif weather_status == "ok" and weather:
        hot_days = [
            day
            for day in weather
            if getattr(day, "t_max_c", None) is not None and day.t_max_c >= 32
        ]
        if hot_days:
            decisions.append(
                ContextDecision(
                    code="live_heat",
                    title="The forecast is hot",
                    why=f"{len(hot_days)} day(s) reach 32°C or more.",
                    effect="On those days, the longer walks stay before midday.",
                )
            )
    decisions.append(
        ContextDecision(
            code="pace",
            title=f"A {profile.trip_pace.lower()} pace",
            why=f"{profile.group_type} group, {profile.activity_level} activity.",
            effect=f"On exploring days, plan on about {slots['sights']} visits and {slots['meals']} meals. Arrival follows the time left after food and rest.",
        )
    )
    if profile.has_children:
        decisions.append(
            ContextDecision(
                code="family",
                title="Planned with children in mind",
                why=f"Traveling with {profile.children} child(ren).",
                effect="Family-friendly stops come first, and long stacked hikes are avoided.",
            )
        )
    if profile.limited_mobility:
        decisions.append(
            ContextDecision(
                code="access",
                title="Easier walking where we can",
                why=", ".join(profile.accessibility_needs) or "Limited mobility noted.",
                effect="We prefer shorter or more accessible stops when the listings say so.",
            )
        )
    rating = profile.accommodation_rating
    if rating and "no pref" not in rating.lower():
        stay_kind = profile.accommodation_type.replace("_", " ") if profile.accommodation_type else "stay"
        decisions.append(
            ContextDecision(
                code="stay_tier",
                title=f"{rating} stays",
                why=f"You asked for {rating} {stay_kind}s.",
                effect="Hotels are taken from listings at that star level when the city has them. If it does not, we use the closest listed tier and say so.",
            )
        )
    decisions.append(
        ContextDecision(
            code="budget",
            title=f"A {band} budget",
            why=f"{profile.total_budget:g} JOD for {profile.duration_days} days.",
            effect=_budget_traveler_effect(band),
        )
    )
    if profile.interests:
        decisions.append(
            ContextDecision(
                code="interests",
                title="Chosen around what you care about",
                why=interest_phrase(profile.interests),
                effect=f"Stops follow {interest_phrase(profile.interests)}. Unrelated places stay off the list.",
            )
        )
    return decisions
