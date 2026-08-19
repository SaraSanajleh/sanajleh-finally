"""Input schemas matching the ReTour Wizard Package Request contract."""
# هاي السكيما شو الانبوت اللي رح يدخل لل ai agent 

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# شرح اكثر وأكثر عن pydantic
"""
طيب لماذا Pydantic؟

لأنه يعمل Validation
يعني:
لو عندك:
age: int
وأرسل المستخدم:
{
 "age": "20"
}
Pydantic يحاول يحولها:

"20"
↓
20
ولو شيء غير منطقي يعطي Error.
"""

class PackageMode(StrEnum):  # StrEnum انه ما في غير هيك بقدر يدخل
    BROWSE = "browse"
    BUILD = "build"


class ArrivalAirport(StrEnum):
    AMM = "AMM"
    AQJ = "AQJ"
    OTHER = "OTHER"


class PreferredLanguage(StrEnum):
    ENGLISH = "English"
    ARABIC = "Arabic"
    FRENCH = "French"
    GERMAN = "German"
    SPANISH = "Spanish"
    ITALIAN = "Italian"


class JordanRegion(StrEnum):
    AMMAN = "Amman"
    PETRA = "Petra"
    WADI_RUM = "Wadi Rum"
    AQABA = "Aqaba"
    DEAD_SEA = "Dead Sea"
    JERASH = "Jerash"
    AJLOUN = "Ajloun"
    MADABA = "Madaba"
    IRBID = "Irbid"


class GroupType(StrEnum):
    SOLO = "solo"
    COUPLE = "couple"
    FAMILY = "family"
    FRIENDS = "friends"
    BUSINESS = "business"


class AccessibilityNeed(StrEnum):
    WHEELCHAIR = "Wheelchair Access"
    LIMITED_WALKING = "Limited Walking"
    VISUAL = "Visual Assistance"
    HEARING = "Hearing Assistance"
    ELDER_FRIENDLY = "Elder Friendly"


class Interest(StrEnum):
    HISTORY = "history"
    NATURE = "nature"
    FOOD = "food"
    CULTURE = "culture"
    ADVENTURE = "adventure"
    SHOPPING = "shopping"
    PHOTOGRAPHY = "photography"
    DESERT = "desert"
    BEACHES = "beaches"
    ART = "art"
    WELLNESS = "wellness"
    HIKING = "hiking"
    CAMPING = "camping"
    LOCAL_EXPERIENCES = "local_experiences"
    FESTIVALS = "festivals"
    ARCHAEOLOGY = "archaeology"
    RELIGIOUS_SITES = "religious_sites"
    CYCLING = "cycling"
    SCENIC_VIEWS = "scenic_views"
    LUXURY = "luxury"
    LOCAL_EVENTS = "local_events"
    ECO_TOURISM = "eco_tourism"
    WILDLIFE = "wildlife"
    MUSEUMS = "museums"


class TripPace(StrEnum):
    RELAXED = "Relaxed"
    BALANCED = "Balanced"
    FAST_PACED = "Fast-paced"
    NO_PREFERENCE = "No Preference"


class ActivityLevel(StrEnum):
    EASY = "Easy"
    MODERATE = "Moderate"
    ACTIVE = "Active"
    NO_PREFERENCE = "No Preference"


class MustVisitLandmark(StrEnum):
    PETRA = "Petra"
    WADI_RUM = "Wadi Rum"
    DEAD_SEA = "Dead Sea"
    JERASH = "Jerash"
    AJLOUN = "Ajloun"
    AQABA = "Aqaba"
    AMMAN = "Amman"
    MADABA = "Madaba"


class AccommodationType(StrEnum):
    NO_PREF = "no_pref"
    HOTEL = "hotel"
    RESORT = "resort"
    BOUTIQUE = "boutique"
    ECO_LODGE = "eco_lodge"
    DESERT_CAMP = "desert_camp"
    UNSPECIFIED = ""


class AccommodationRating(StrEnum):
    NO_PREFERENCE = "No Preference"
    THREE_STAR = "3 star"
    FOUR_STAR = "4 star"
    FIVE_STAR = "5 star"
    UNSPECIFIED = ""


class Cuisine(StrEnum):
    LOCAL_JORDANIAN = "Local Jordanian"
    MIDDLE_EASTERN = "Middle Eastern"
    INTERNATIONAL = "International"
    VEGETARIAN = "Vegetarian"
    VEGAN = "Vegan"
    HALAL = "Halal"
    SEAFOOD = "Seafood"
    FINE_DINING = "Fine Dining"
    STREET_FOOD = "Street Food"


class SpecialOccasion(StrEnum):
    NONE = "None"
    BIRTHDAY = "Birthday"
    HONEYMOON = "Honeymoon"
    ANNIVERSARY = "Anniversary"
    GRADUATION = "Graduation"
    FAMILY_CELEBRATION = "Family Celebration"
    UNSPECIFIED = ""


class SMEPreference(StrEnum):
    FAMILY_OWNED = "Family-owned Businesses"
    ECO_FRIENDLY = "Eco-friendly SMEs"
    HIGHLY_RATED = "Highly Rated SMEs"
    WOMEN_LED = "Women-led Businesses"
    COMMUNITY_TOURISM = "Community-based Tourism"
    LUXURY_SERVICES = "Luxury Services"


class AIPriority(StrEnum):
    BUDGET = "budget"
    FAMOUS = "famous"
    HIDDEN = "hidden"
    AUTHENTIC = "authentic"
    SUSTAINABLE = "sustainable"
    COMFORT = "comfort"
    MAXIMIZE = "maximize"
    FAMILY = "family"
    UNSPECIFIED = ""


STANDARD_DURATIONS = {"1", "2", "3", "5", "7"}


class TripDetails(BaseModel):
    """Trip timing, budget, and location preferences."""

    startDate: date
    duration: str
    arrivalAirport: ArrivalAirport # بس بقبل الخيارات الموجودة
    arrivalTime: str = "14:00"
    totalBudget: float = Field(ge=0)  # float لانه مصاري وال ge يا اما greater than or equal to 0 عشان امنع القيم السالبة
    # Field  بتسمحلي اضيف شرط
    preferredLanguage: PreferredLanguage # الخيارات الموجودة
    preferredRegions: list[JordanRegion] = Field(default_factory=list)

    @field_validator("duration") # هون تشييك ع ادخال المستخدم لل duration
    @classmethod
    def validate_duration(cls, value: str) -> str:
        if value in STANDARD_DURATIONS:
            return value
        if value.isdigit() and int(value) > 0:
            return value
        raise ValueError(
            f"duration must be one of {sorted(STANDARD_DURATIONS)} or a positive custom day count"
        )

    @field_validator("arrivalTime")
    @classmethod
    def validate_arrival_time(cls, value: str) -> str:
        text = (value or "14:00").strip()
        parts = text.split(":")
        if len(parts) < 2:
            raise ValueError("arrivalTime must be HH:MM")
        try:
            hour = int(parts[0])
            minute = int(parts[1][:2])
        except ValueError as exc:
            raise ValueError("arrivalTime must be HH:MM") from exc
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("arrivalTime must be a real clock time")
        return f"{hour:02d}:{minute:02d}"


class TravelersDetails(BaseModel): #معلومات الأشخاص الذين سيذهبون في الرحلة.
    """Traveler composition and accessibility needs."""

    adults: int = Field(ge=1, le=20)
    children: int = Field(ge=0, le=20)
    childrenAges: list[str | int] = Field(default_factory=list)
    seniors: int = Field(ge=0, le=20)
    groupType: GroupType # من الخيارات الموجودة
    accessibilityNeeds: list[AccessibilityNeed] = Field(default_factory=list)
    """
    إذا لم يوجد أطفال:ا اجعلها []
    بدل ما تكون:
    None
    """

    @model_validator(mode="after")
    def validate_children_ages_length(self) -> TravelersDetails:
        if len(self.childrenAges) != self.children:
            raise ValueError("childrenAges length must equal children count")
        return self
    """
    هذا عشان يتأكد انه عدد الأطفال مساوي لعدد الاعمار اللي دخلهم اليوزر
    "children":3,
    "childrenAges":[5,8,12]
    """


class PreferencesDetails(BaseModel):
    """Activity and destination preferences."""

    interests: list[Interest] = Field(min_length=1) # "interests":[] مرفوض تكون فاضية اهتمام السائح لازم يدخل ع الأقل اهتمام واحد
    tripPace: TripPace
    activityLevel: ActivityLevel
    mustVisit: list[MustVisitLandmark] = Field(default_factory=list)
    placesToAvoid: str = ""


class AccommodationDetails(BaseModel):
    """Accommodation preferences."""

    type: AccommodationType = AccommodationType.UNSPECIFIED # اذا المستخدم ما حدد بخليها unspecified
    rating: AccommodationRating = AccommodationRating.UNSPECIFIED


class DiningDetails(BaseModel):
    """Dining preferences."""

    cuisine: list[Cuisine] = Field(default_factory=list)


class ExtrasDetails(BaseModel):
    """Additional context and AI prioritization hints."""

    specialOccasion: SpecialOccasion = SpecialOccasion.UNSPECIFIED
    smePreferences: list[SMEPreference] = Field(default_factory=list)
    aiPriority: AIPriority = AIPriority.UNSPECIFIED
    freeText: str = ""

'''
هذا هو الطلب الكامل الذي يصل للـ Agent. يعني هو الأب
'''
class PackageRequest(BaseModel):
    """Full wizard payload sent to the Package Builder Agent."""

    mode: PackageMode
    requestedAt: datetime
    trip: TripDetails
    travelers: TravelersDetails
    preferences: PreferencesDetails
    accommodation: AccommodationDetails = Field(default_factory=AccommodationDetails)
    dining: DiningDetails = Field(default_factory=DiningDetails)
    extras: ExtrasDetails = Field(default_factory=ExtrasDetails)

    @property
    def duration_days(self) -> int:
        return int(self.trip.duration)

    @property
    def total_travelers(self) -> int:
        return self.travelers.adults + self.travelers.children + self.travelers.seniors
