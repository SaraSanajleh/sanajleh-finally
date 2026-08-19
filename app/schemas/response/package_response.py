"""Tourism Package output schema — structured, validated, frontend-friendly."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


def _unknown(value: object) -> str:
    if value is None:
        return "not_available"
    text = str(value).strip()
    return text or "not_available"


class GeoPoint(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    precision: str = "unknown"


class SourceRef(BaseModel):
    dataset: str = "unknown"
    record_id: str = "unknown"


class ConstraintUnmet(BaseModel):
    item: str
    reason: str
    reason_code: str = "unspecified"


class ConstraintStatus(BaseModel):
    status: str = "satisfied"
    unmet: list[ConstraintUnmet] = Field(default_factory=list)


class TripOverview(BaseModel):
    title: str = ""
    summary: str = ""
    start_date: str = ""
    end_date: str = ""
    duration_days: int = 1
    nights: int = 0
    regions: list[str] = Field(default_factory=list)
    arrival_airport: str = ""
    language: str = "English"


class TravelerProfileOut(BaseModel):
    group_type: str = ""
    adults: int = 1
    children: int = 0
    children_ages: list[int] = Field(default_factory=list)
    seniors: int = 0
    total_travelers: int = 1
    interests: list[str] = Field(default_factory=list)
    pace: str = ""
    activity_level: str = ""
    accessibility_needs: list[str] = Field(default_factory=list)


class PlanningDecision(BaseModel):
    code: str = ""
    title: str = ""
    why: str = ""
    effect: str = ""


class PlanningMeta(BaseModel):
    strategy: str = ""
    constraints: dict[str, Any] = Field(default_factory=dict)
    constraint_status: ConstraintStatus = Field(default_factory=ConstraintStatus)
    assumptions: list[str] = Field(default_factory=list)
    climate: dict[str, Any] = Field(default_factory=dict)
    weather_status: str = "unknown"
    decisions: list[PlanningDecision] = Field(default_factory=list)


class ScheduleItem(BaseModel):
    time: str = ""
    end_time: str = ""
    slot: str = ""
    type: str = "poi"
    item_id: str = ""
    name: str = ""
    duration_minutes: int | None = None
    location: str = ""
    coordinates: GeoPoint | None = None
    description: str = ""
    reason: str = ""
    matched_preferences: list[str] = Field(default_factory=list)
    estimated_cost: str = "not_available"
    source: SourceRef | None = None
    confidence: str = "medium"

    @field_validator("estimated_cost", mode="before")
    @classmethod
    def cost_unknown(cls, value: object) -> str:
        return _unknown(value)


class SMESpec(BaseModel):
    label: str
    value: str


class DaySME(BaseModel):
    sme_id: str = ""
    sme_type: str = "unknown"
    name: str = ""
    role: str = ""
    location: str = ""
    experience_type: str = ""
    match_score: float = 0.0
    reason: str = ""
    matched_because: list[str] = Field(default_factory=list)
    known_for: list[str] = Field(default_factory=list)
    specializations: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    experience_years: int | None = None
    destinations_covered: list[str] = Field(default_factory=list)
    covers_regions: list[str] = Field(default_factory=list)
    package_role: str = ""
    specs: list[SMESpec] = Field(default_factory=list)
    source: SourceRef | None = None
    coordinates: GeoPoint | None = None


class DayPlan(BaseModel):
    day: int = 1
    date: str = ""

    @field_validator("day", mode="before")
    @classmethod
    def coerce_day(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return value
    region: str = ""
    theme: str = ""
    summary: str = ""
    is_arrival_day: bool = False
    schedule: list[ScheduleItem] = Field(default_factory=list)
    smes: list[DaySME] = Field(default_factory=list)
    transport_notes: str = "not_available"


class BudgetLine(BaseModel):
    category: str
    estimated_cost: str = "not_available"
    notes: str = ""
    confidence: str = "low"


class BudgetOverview(BaseModel):
    currency: str = "JOD"
    traveler_budget: float | None = None
    estimated_total: str = "not_available"
    band: str = "unknown"
    items: list[BudgetLine] = Field(default_factory=list)
    disclaimer: str = "We only show amounts when a listing includes a price."


class SMEValueProposition(BaseModel):
    headline: str = "Local businesses recommended for this trip"
    summary: str = ""
    recommended: list[DaySME] = Field(default_factory=list)


class PackageWarning(BaseModel):
    code: str = "note"
    message: str = ""
    severity: str = "info"

    @model_validator(mode="before")
    @classmethod
    def coerce_warning(cls, value: object) -> object:
        if isinstance(value, str):
            return {"code": "note", "message": value, "severity": "info"}
        if isinstance(value, dict):
            data = dict(value)
            message = str(data.get("message") or data.get("text") or data.get("warning") or "")
            data["message"] = message
            data.setdefault("code", "note")
            data.setdefault("severity", "info")
            return data
        return value


class Explainability(BaseModel):
    trip_planning_reason: str = ""
    highlights: list[str] = Field(default_factory=list)
    why_smes: list[str] = Field(default_factory=list)
    context_benefits: list[str] = Field(default_factory=list)


class TourismPackage(BaseModel):
    """Validated tourism package returned to the API and UI."""

    package_id: str = ""
    status: str = "complete"
    welcome_message: str = ""
    trip_title: str = ""
    trip: TripOverview = Field(default_factory=TripOverview)
    traveler_profile: TravelerProfileOut = Field(default_factory=TravelerProfileOut)
    planning: PlanningMeta = Field(default_factory=PlanningMeta)
    days: list[DayPlan] = Field(default_factory=list)
    budget: BudgetOverview = Field(default_factory=BudgetOverview)
    sme_value: SMEValueProposition = Field(default_factory=SMEValueProposition)
    sources: list[SourceRef] = Field(default_factory=list)
    warnings: list[PackageWarning] = Field(default_factory=list)
    explanations: Explainability = Field(default_factory=Explainability)

    @model_validator(mode="after")
    def sync_title(self) -> TourismPackage:
        if not self.trip_title and self.trip.title:
            self.trip_title = self.trip.title
        if not self.trip.title and self.trip_title:
            self.trip.title = self.trip_title
        return self


class RagClusterPreview(BaseModel):
    cluster_id: int | None = None
    theme: str = ""
    poi_count: int = 0
    hotel_count: int = 0
    event_count: int = 0
    poi_names: list[str] = Field(default_factory=list)
    hotel_names: list[str] = Field(default_factory=list)
    sample_restaurants: list[str] = Field(default_factory=list)
    event_names: list[str] = Field(default_factory=list)


class RagEvaluationSummary(BaseModel):
    status: str = "unknown"
    source: str | None = None
    duration_days: int | None = None
    cluster_count: int = 0
    clusters: list[RagClusterPreview] = Field(default_factory=list)


class BrainTrace(BaseModel):
    stages: list[str] = Field(default_factory=list)
    stage_ms: dict[str, float] = Field(default_factory=dict)
    planner_fast_mode: bool = False
    planner_fast_polish: bool = False
    knowledge_counts: dict[str, int] = Field(default_factory=dict)
    sme_counts: dict[str, int] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)


class PackageGenerationMetadata(BaseModel):
    model: str
    provider: str
    mode: str
    latencyMs: float
    retries: int = 0
    caseId: str | None = None
    rag: RagEvaluationSummary | None = None
    trace: BrainTrace | None = None


class PackageGenerationResponse(BaseModel):
    success: bool = True
    package: TourismPackage
    metadata: PackageGenerationMetadata
    knowledge: dict[str, Any] | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
