"""Sample payloads for tests."""

from __future__ import annotations

VALID_PACKAGE_REQUEST = {
    "mode": "build",
    "requestedAt": "2025-07-14T10:30:00.000Z",
    "trip": {
        "startDate": "2025-08-15",
        "duration": "5",
        "arrivalAirport": "AMM",
        "arrivalTime": "10:00",
        "totalBudget": 1500,
        "preferredLanguage": "English",
        "preferredRegions": ["Petra", "Wadi Rum", "Dead Sea"],
    },
    "travelers": {
        "adults": 2,
        "children": 0,
        "childrenAges": [],
        "seniors": 0,
        "groupType": "couple",
        "accessibilityNeeds": [],
    },
    "preferences": {
        "interests": ["history", "photography", "hiking", "food"],
        "tripPace": "Balanced",
        "activityLevel": "Moderate",
        "mustVisit": ["Petra", "Dead Sea"],
        "placesToAvoid": "",
    },
    "accommodation": {"type": "boutique", "rating": "4 star"},
    "dining": {"cuisine": ["Local Jordanian", "Fine Dining"]},
    "extras": {
        "specialOccasion": "Anniversary",
        "smePreferences": ["Family-owned Businesses"],
        "aiPriority": "authentic",
        "freeText": "We celebrate our 5th anniversary.",
    },
}

VALID_PACKAGE_RESPONSE = {
    "package_id": "pkg-test-001",
    "status": "complete",
    "welcome_message": "Welcome! Here is a balanced Jordan journey crafted for your anniversary.",
    "trip_title": "Anniversary Jordan Discovery",
    "trip": {
        "title": "Anniversary Jordan Discovery",
        "summary": "A romantic history-focused trip through Petra and the Dead Sea.",
        "start_date": "2025-08-15",
        "end_date": "2025-08-19",
        "duration_days": 5,
        "nights": 4,
        "regions": ["Petra", "Wadi Rum", "Dead Sea"],
        "arrival_airport": "AMM",
        "language": "English",
    },
    "traveler_profile": {
        "group_type": "couple",
        "adults": 2,
        "children": 0,
        "children_ages": [],
        "seniors": 0,
        "total_travelers": 2,
        "interests": ["history", "photography", "hiking", "food"],
        "pace": "Balanced",
        "activity_level": "Moderate",
        "accessibility_needs": [],
    },
    "planning": {
        "strategy": "Cluster days around Petra, Wadi Rum, and the Dead Sea.",
        "constraints": {"must_visit": ["Petra", "Dead Sea"]},
        "constraint_status": {"status": "satisfied", "unmet": []},
        "assumptions": ["Travel times are qualitative."],
        "weather_status": "unknown",
    },
    "days": [
        {
            "day": 1,
            "date": "2025-08-15",
            "region": "Petra",
            "theme": "Petra heritage",
            "summary": "Walk the Siq and Treasury at a balanced pace.",
            "schedule": [
                {
                    "time": "08:00",
                    "end_time": "12:00",
                    "slot": "morning",
                    "type": "poi",
                    "item_id": "poi_test_petra",
                    "name": "Petra Visitor Center",
                    "location": "Wadi Musa",
                    "description": "Start the Petra day from the official visitor area.",
                    "reason": "Matches your history and photography interests.",
                    "matched_preferences": ["history", "photography"],
                    "estimated_cost": "not_available",
                    "source": {"dataset": "pois", "record_id": "poi_test_petra"},
                    "confidence": "high",
                }
            ],
            "smes": [
                {
                    "sme_id": "SME-000001",
                    "sme_type": "tour_guide",
                    "name": "Ahmad Momani",
                    "role": "Local guide",
                    "location": "Ajloun",
                    "match_score": 0.72,
                    "reason": "History and nature specialist",
                    "matched_because": ["Matches interests: history"],
                    "source": {"dataset": "sme_guides", "record_id": "SME-000001"},
                }
            ],
            "transport_notes": "not_available",
        }
    ],
    "budget": {
        "currency": "JOD",
        "traveler_budget": 1500,
        "estimated_total": "not_available",
        "band": "moderate",
        "items": [
            {"category": "Accommodation", "estimated_cost": "not_available", "notes": ""},
            {"category": "Meals", "estimated_cost": "not_available", "notes": ""},
        ],
        "disclaimer": "Amounts are shown only when catalog evidence exists.",
    },
    "sme_value": {
        "headline": "Local businesses recommended for this trip",
        "summary": "Relevant guides matched to your interests and regions.",
        "recommended": [],
    },
    "sources": [{"dataset": "pois", "record_id": "poi_test_petra"}],
    "warnings": [],
    "explanations": {
        "trip_planning_reason": "Prioritized must-visit sites within your stated budget band.",
        "highlights": ["Petra first", "Dead Sea later"],
        "why_smes": ["Guides selected only when they cover your regions."],
    },
}
