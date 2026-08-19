"""Structured planning context — never a free-text blob."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WeatherDay(BaseModel):
    date: str
    t_min_c: float | None = None
    t_max_c: float | None = None
    precipitation_probability: float | None = None
    condition: str = "unknown"
    source: str = "not_available"


class ClimateWindow(BaseModel):
    month: int
    season: str
    typical_pattern: str
    outdoor_guidance: str
    heat_risk: str


class GeographicFrame(BaseModel):
    arrival_airport: str
    preferred_regions: list[str] = Field(default_factory=list)
    region_keys: list[str] = Field(default_factory=list)
    must_visit: list[str] = Field(default_factory=list)
    places_to_avoid: list[str] = Field(default_factory=list)
    clustering_rule: str = (
        "Keep each day geographically coherent. Avoid unnecessary cross-country hops."
    )


class TravelerFrame(BaseModel):
    group_type: str
    adults: int
    children: int = 0
    children_ages: list[int] = Field(default_factory=list)
    seniors: int = 0
    total_travelers: int
    accessibility_needs: list[str] = Field(default_factory=list)
    limited_mobility: bool = False
    family_mode: bool = False


class PaceFrame(BaseModel):
    trip_pace: str
    activity_level: str
    sights_per_day: int
    meals_per_day: int
    max_schedule_items: int


class BudgetFrame(BaseModel):
    total: float
    currency: str = "JOD"
    band: str
    per_day: float
    guidance: str


class ContextDecision(BaseModel):
    """A visible planning choice the traveler can understand."""

    code: str
    title: str
    why: str
    effect: str


class DayIntent(BaseModel):
    """What this calendar day is allowed to contain."""

    day: int
    date: str
    region: str
    region_key: str
    theme: str
    is_must_visit: bool = False
    stay_index: int = 0
    outdoor_window: str = "morning"
    indoor_window: str = "afternoon"
    sights: int = 3
    meals: int = 3
    heat_note: str = ""
    overnight_key: str = ""
    overnight_region: str = ""
    is_arrival_day: bool = False
    stay_style: str = "in_region"
    rest_hours: int = 0
    allow_arrival_activities: bool = False
    arrival_time: str = ""
    paired_key: str = ""


class PlanningContext(BaseModel):
    """Deterministic structured context consumed by the planner."""

    trip_window: dict[str, Any]
    geographic: GeographicFrame
    traveler: TravelerFrame
    pace: PaceFrame
    budget: BudgetFrame
    climate: ClimateWindow
    weather: list[WeatherDay] = Field(default_factory=list)
    weather_status: str = "unknown"
    decision_rules: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    decisions: list[ContextDecision] = Field(default_factory=list)
    day_intents: list[DayIntent] = Field(default_factory=list)

    def prompt_dict(self) -> dict[str, Any]:
        return {
            "trip_window": self.trip_window,
            "geographic": self.geographic.model_dump(mode="json"),
            "traveler": self.traveler.model_dump(mode="json"),
            "pace": self.pace.model_dump(mode="json"),
            "budget": self.budget.model_dump(mode="json"),
            "climate": self.climate.model_dump(mode="json"),
            "weather": [item.model_dump(mode="json") for item in self.weather],
            "weather_status": self.weather_status,
            "decisions": [item.model_dump(mode="json") for item in self.decisions],
            "day_intents": [item.model_dump(mode="json") for item in self.day_intents],
            "decision_rules": self.decision_rules,
            "assumptions": self.assumptions,
            "unknowns": self.unknowns,
        }
