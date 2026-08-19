"""Flatten Alpha PackageRequest → Beta WizardRequest dict (no Beta code changes)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from app.schemas.request.package_request import PackageRequest


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return value


def package_request_to_wizard_payload(request: PackageRequest) -> dict[str, Any]:
    """
    Map nested PackageRequest to flat WizardRequest fields expected by
    POST /api/v1/knowledge/search (Team Beta). Structural flatten only.
    """
    trip = request.trip
    travelers = request.travelers
    preferences = request.preferences
    accommodation = request.accommodation
    dining = request.dining
    extras = request.extras

    return {
        "startDate": trip.startDate.isoformat(),
        "duration": trip.duration,
        "customDuration": "",
        "arrivalAirport": _enum_value(trip.arrivalAirport),
        "arrivalTime": getattr(trip, "arrivalTime", None) or "14:00",
        "totalBudget": float(trip.totalBudget),
        "preferredLanguage": _enum_value(trip.preferredLanguage),
        "preferredRegion": [_enum_value(region) for region in trip.preferredRegions],
        "adults": travelers.adults,
        "children": travelers.children,
        "childrenAges": [str(age) for age in travelers.childrenAges],
        "seniors": travelers.seniors,
        "groupType": _enum_value(travelers.groupType),
        "accessibilityNeeds": [
            _enum_value(need) for need in travelers.accessibilityNeeds
        ],
        "interests": [_enum_value(interest) for interest in preferences.interests],
        "tripPace": _enum_value(preferences.tripPace),
        "activityLevel": _enum_value(preferences.activityLevel),
        "mustVisit": [_enum_value(place) for place in preferences.mustVisit],
        "placesToAvoid": preferences.placesToAvoid or "",
        "accommodationType": _enum_value(accommodation.type),
        "hotelRating": _enum_value(accommodation.rating),
        "cuisine": [_enum_value(item) for item in dining.cuisine],
        "specialOccasion": _enum_value(extras.specialOccasion),
        "smePreferences": [_enum_value(item) for item in extras.smePreferences],
        "aiPriority": _enum_value(extras.aiPriority),
        "freeText": extras.freeText or "",
    }
