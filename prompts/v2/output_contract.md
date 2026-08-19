Return exactly this JSON shape. Use empty arrays / "not_available" rather than invented values.

{
  "package_id": "string",
  "status": "complete|partial",
  "welcome_message": "short welcome",
  "trip_title": "short title",
  "trip": {
    "title": "same title",
    "summary": "2-3 sentences",
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "duration_days": 0,
    "nights": 0,
    "regions": [],
    "arrival_airport": "AMM",
    "language": "English"
  },
  "traveler_profile": {
    "group_type": "",
    "adults": 1,
    "children": 0,
    "children_ages": [],
    "seniors": 0,
    "total_travelers": 1,
    "interests": [],
    "pace": "",
    "activity_level": "",
    "accessibility_needs": []
  },
  "planning": {
    "strategy": "one sentence",
    "constraints": {},
    "constraint_status": {"status": "satisfied", "unmet": []},
    "assumptions": [],
    "climate": {},
    "weather_status": "unknown"
  },
  "days": [
    {
      "day": 1,
      "date": "YYYY-MM-DD",
      "region": "",
      "theme": "",
      "summary": "",
      "schedule": [
        {
          "time": "09:00",
          "end_time": "11:00",
          "slot": "morning",
          "type": "poi|restaurant|hotel|activity",
          "item_id": "catalog-id",
          "name": "",
          "duration_minutes": 120,
          "location": "",
          "description": "",
          "reason": "",
          "matched_preferences": [],
          "estimated_cost": "not_available",
          "source": {"dataset": "pois", "record_id": "catalog-id"},
          "confidence": "high"
        }
      ],
      "smes": [],
      "transport_notes": "not_available"
    }
  ],
  "budget": {
    "currency": "JOD",
    "traveler_budget": 0,
    "estimated_total": "not_available",
    "band": "moderate",
    "items": [],
    "disclaimer": "Amounts are shown only when catalog evidence exists."
  },
  "sme_value": {
    "headline": "Local businesses recommended for this trip",
    "summary": "",
    "recommended": []
  },
  "sources": [],
  "warnings": [],
  "explanations": {
    "trip_planning_reason": "",
    "highlights": [],
    "why_smes": []
  }
}
