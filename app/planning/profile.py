"""Normalize the Wizard PackageRequest into an internal TouristProfile."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel, Field

from app.planning.geo import region_key, wizard_region_keys
from app.schemas.request.package_request import PackageRequest


class TouristProfile(BaseModel):
    """Internal planning representation. Wizard contract stays unchanged."""

    mode: str
    start_date: date
    duration_days: int
    exploration_days: int
    nights: int
    end_date: date
    arrival_airport: str
    arrival_time: str = "14:00"
    total_budget: float
    currency: str = "JOD"
    preferred_language: str
    preferred_regions: list[str] = Field(default_factory=list)
    region_keys: list[str] = Field(default_factory=list)
    adults: int
    children: int
    children_ages: list[int] = Field(default_factory=list)
    seniors: int
    total_travelers: int
    group_type: str
    accessibility_needs: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    trip_pace: str
    activity_level: str
    must_visit: list[str] = Field(default_factory=list)
    places_to_avoid: list[str] = Field(default_factory=list)
    accommodation_type: str = ""
    accommodation_rating: str = ""
    cuisine: list[str] = Field(default_factory=list)
    special_occasion: str = ""
    sme_preferences: list[str] = Field(default_factory=list)
    ai_priority: str = ""
    free_text: str = ""
    has_children: bool = False
    has_seniors: bool = False
    limited_mobility: bool = False

    def prompt_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _parse_avoid_list(raw: str) -> list[str]:
    if not raw or not raw.strip():
        return []
    parts = [p.strip() for p in raw.replace(";", ",").split(",")]
    return [p for p in parts if p]


def _ages(values: list[str | int]) -> list[int]:
    ages: list[int] = []
    for value in values:
        try:
            ages.append(int(str(value).strip()))
        except (TypeError, ValueError):
            continue
    return ages


def normalize_tourist_profile(request: PackageRequest) -> TouristProfile:
    exploration = max(int(request.duration_days), 1)
    calendar = exploration + 1
    start = request.trip.startDate
    avoid = _parse_avoid_list(request.preferences.placesToAvoid)
    regions = [r.value for r in request.trip.preferredRegions]
    keys = sorted(wizard_region_keys(regions + [m.value for m in request.preferences.mustVisit]))
    accessibility = [a.value for a in request.travelers.accessibilityNeeds]
    limited = any(
        need.lower() in {"wheelchair access", "limited walking", "elder friendly"}
        for need in accessibility
    )
    return TouristProfile(
        mode=request.mode.value,
        start_date=start,
        duration_days=calendar,
        exploration_days=exploration,
        nights=exploration,
        end_date=start + timedelta(days=exploration),
        arrival_airport=request.trip.arrivalAirport.value,
        arrival_time=getattr(request.trip, "arrivalTime", None) or "14:00",
        total_budget=float(request.trip.totalBudget),
        preferred_language=request.trip.preferredLanguage.value,
        preferred_regions=regions,
        region_keys=keys,
        adults=request.travelers.adults,
        children=request.travelers.children,
        children_ages=_ages(request.travelers.childrenAges),
        seniors=request.travelers.seniors,
        total_travelers=request.total_travelers,
        group_type=request.travelers.groupType.value,
        accessibility_needs=accessibility,
        interests=[i.value for i in request.preferences.interests],
        trip_pace=request.preferences.tripPace.value,
        activity_level=request.preferences.activityLevel.value,
        must_visit=[m.value for m in request.preferences.mustVisit],
        places_to_avoid=avoid,
        accommodation_type=request.accommodation.type.value,
        accommodation_rating=request.accommodation.rating.value,
        cuisine=[c.value for c in request.dining.cuisine],
        special_occasion=request.extras.specialOccasion.value,
        sme_preferences=[s.value for s in request.extras.smePreferences],
        ai_priority=request.extras.aiPriority.value,
        free_text=request.extras.freeText or "",
        has_children=request.travelers.children > 0,
        has_seniors=request.travelers.seniors > 0,
        limited_mobility=limited,
    )


def requested_stars(rating: str) -> float | None:
    text = (rating or "").strip().lower()
    if not text or "no pref" in text:
        return None
    for char in text:
        if char.isdigit():
            return float(char)
    return None


def budget_band(total_budget: float, days: int) -> str:
    if days <= 0:
        return "unknown"
    per_day = total_budget / days
    if per_day < 80:
        return "value"
    if per_day < 180:
        return "moderate"
    if per_day < 350:
        return "comfort"
    return "premium"


def pace_slots(pace: str) -> dict[str, int]:
    """How many major sights a day should carry. Meals are breakfast, lunch, dinner."""
    key = (pace or "").lower()
    if "relax" in key:
        return {"sights": 3, "meals": 3, "max_schedule": 10}
    if "fast" in key:
        return {"sights": 6, "meals": 3, "max_schedule": 12}
    return {"sights": 5, "meals": 3, "max_schedule": 11}


def region_overlap(entity_region: str, profile: TouristProfile) -> bool:
    key = region_key(entity_region)
    if not profile.region_keys:
        return True
    return key in set(profile.region_keys) or any(
        key and key in allowed for allowed in profile.region_keys
    )
