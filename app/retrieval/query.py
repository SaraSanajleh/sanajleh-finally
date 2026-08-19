"""Build a tourism retrieval query from the locked day + traveler profile."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.context.models import DayIntent
from app.planning.profile import TouristProfile, requested_stars


class DayRetrievalQuery(BaseModel):
    """What this day is allowed to retrieve. Not a free-text search string."""

    day: int
    region: str
    region_key: str
    theme: str = ""
    interests: list[str] = Field(default_factory=list)
    cuisine: list[str] = Field(default_factory=list)
    group_type: str = ""
    has_children: bool = False
    limited_mobility: bool = False
    avoid: list[str] = Field(default_factory=list)
    sights: int = 3
    meals: int = 2
    stay_index: int = 0
    is_must_visit: bool = False
    overnight_key: str = ""
    heat_risk: bool = False
    need_hotel: bool = False
    is_arrival_day: bool = False
    hotel_stars: float | None = None
    accommodation_type: str = ""
    used_ids: list[str] = Field(default_factory=list)
    visit_keys: list[str] = Field(default_factory=list)

    def prompt_dict(self) -> dict:
        return self.model_dump(mode="json")


def build_day_query(
    profile: TouristProfile,
    intent: DayIntent,
    *,
    heat_risk: bool = False,
    need_hotel: bool = False,
    used_ids: set[str] | None = None,
) -> DayRetrievalQuery:
    visit_keys = [intent.region_key]
    if getattr(intent, "paired_key", ""):
        visit_keys.append(intent.paired_key)
    return DayRetrievalQuery(
        day=intent.day,
        region=intent.region,
        region_key=intent.region_key,
        theme=intent.theme,
        interests=list(profile.interests),
        cuisine=list(profile.cuisine),
        group_type=profile.group_type,
        has_children=profile.has_children,
        limited_mobility=profile.limited_mobility,
        avoid=list(profile.places_to_avoid),
        sights=intent.sights,
        meals=intent.meals,
        stay_index=intent.stay_index,
        is_must_visit=intent.is_must_visit,
        heat_risk=heat_risk,
        need_hotel=need_hotel,
        overnight_key=intent.overnight_key or intent.region_key,
        is_arrival_day=intent.is_arrival_day,
        hotel_stars=requested_stars(profile.accommodation_rating),
        accommodation_type=profile.accommodation_type,
        used_ids=sorted(used_ids or set()),
        visit_keys=visit_keys,
    )
