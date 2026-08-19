"""
ReTour Retriever — API schemas (Pydantic V2).

Input  = the raw wizard.
Output = the FINAL, committed evidence-package contract for the planning agent.

Design intent (locked with Team Alpha):
  - This JSON SHAPE is final. Future improvements make the retriever STRONGER
    (better search / ranking / selection) but do NOT change this shape, so the
    agent prompt built on it never breaks.
  - Every field must support an agent DECISION (choose / schedule / cost / route /
    explain). No decorative fields (context-length research: extra tokens hurt a
    small model's multi-hop reasoning even within budget).
  - `location` is FLAT (region/city/district/address/lat/lon) — easiest and safest
    for a small model to read.
  - `facts` is a curated, type-specific dict of decision-supporting fields.
  - `why_retrieved` is the alignment record: which explicit wizard fields this
    entity satisfies (why the user will like it).
  - Ordering matters (lost-in-the-middle): clusters, then anchors before discovery,
    strongest first; within a card the identity + why + location come first.
"""
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, field_validator


class WizardRequest(BaseModel):
    # required
    startDate: str
    duration: str
    arrivalAirport: str
    arrivalTime: Optional[str] = "14:00"
    adults: int
    children: int
    seniors: int
    groupType: str
    interests: List[str]
    totalBudget: float
    # optional (defaults so a partial wizard still validates)
    customDuration: Optional[str] = ""
    preferredLanguage: Optional[str] = None
    preferredRegion: List[str] = Field(default_factory=list)
    childrenAges: List[str] = Field(default_factory=list)
    accessibilityNeeds: List[str] = Field(default_factory=list)
    tripPace: Optional[str] = None
    activityLevel: Optional[str] = None
    mustVisit: List[str] = Field(default_factory=list)
    placesToAvoid: Optional[str] = ""
    accommodationType: Optional[str] = None
    hotelRating: Optional[str] = None
    cuisine: List[str] = Field(default_factory=list)
    specialOccasion: Optional[str] = None
    smePreferences: List[str] = Field(default_factory=list)
    aiPriority: Optional[str] = None
    freeText: Optional[str] = ""


class EntityCard(BaseModel):
    id: str
    entity_type: str
    name: str
    role: str = ""                       # "anchor" | "discovery" | "" (rest/hotel/event)
    # flat location (easiest for a small model)
    region: str = ""
    city: str = ""
    district: str = ""
    address: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # alignment record: which explicit wizard fields this entity satisfies
    why_retrieved: List[str] = Field(default_factory=list)
    # curated, type-specific, decision-supporting planning fields
    facts: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("region", "city", "district", "address", "role", "name", mode="before")
    @classmethod
    def _none_to_empty(cls, value: Any) -> Any:
        """Knowledge blobs sometimes emit null for string location fields."""
        return "" if value is None else value


class DistanceRef(BaseModel):
    """Explicit intra-day distance so the agent can sequence/route without guessing."""
    poi_id: str
    km: float


class PoiNode(BaseModel):
    poi: EntityCard
    restaurants: List[EntityCard] = Field(default_factory=list)
    # False = no suitable nearby restaurant -> agent plans meals around another POI
    dining_available: bool = True
    # distance (km) from this POI to every other POI in the same day, nearest first
    distances_to_others: List[DistanceRef] = Field(default_factory=list)


class Cluster(BaseModel):
    cluster_id: int
    theme: str = ""                      # day identity: region + interests satisfied
    pois: List[PoiNode] = Field(default_factory=list)   # anchors first, strongest first
    hotels: List[EntityCard] = Field(default_factory=list)   # cluster level (region)
    events: List[EntityCard] = Field(default_factory=list)   # cluster level (region)
    summary: str = ""                    # one-line deterministic recap


class SearchResponse(BaseModel):
    duration_days: int
    clusters: List[Cluster] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)