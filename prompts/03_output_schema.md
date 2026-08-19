# Final Assembled Package JSON Schema

Return **one JSON object** with exactly this structure in a single response.
Do not add, remove, rename, or re-nest fields.
Do not split the package across multiple replies.

```json
{
  "welcome_message": "",

  "why_you_will_love_this": {
    "highlights": [],
    "special_touches": []
  },

  "trip_title": "",

  "trip_description": {
    "overview": "",
    "included": [],
    "not_included": []
  },

  "trip_details": {
    "duration": {
      "days": "",
      "nights": ""
    },
    "trip_type": [],
    "number_of_travelers": "",
    "budget": {
      "amount": "",
      "currency": "JOD"
    }
  },

  "daily_itinerary": [
    {
      "day_number": "",
      "day_title": "",
      "day_summary": "",
      "activities": [
        {
          "start_time": "",
          "end_time": "",
          "activity_title": "",
          "description": "",
          "location": "",
          "estimated_cost": "",
          "smart_tip": ""
        }
      ],
      "activity_alternatives": [
        {
          "original_activity": "",
          "alternative_activity": "",
          "reason": ""
        }
      ]
    }
  ],

  "budget_summary": {
    "items": [
      {
        "category": "",
        "estimated_cost": "",
        "notes": ""
      }
    ],
    "total_estimated_cost": ""
  },

  "Essential Travel Tips": [
    {
      "category": "",
      "tips": []
    }
  ],

  "explanations": {
    "trip_planning_reason": "",
    "selection_reason": ""
  }
}
```

## Field constraints (match API schema)
- `why_you_will_love_this` MUST be `{ "highlights": [string,...], "special_touches": [string,...] }` — never theme keys like culture/history/nature
- `trip_description` MUST be `{ "overview": string, "included": [string,...], "not_included": [string,...] }` — not a bare string
- `Essential Travel Tips` MUST be an array of `{ "category": string, "tips": [string,...] }` — not a dict of categories
- `explanations` MUST be `{ "trip_planning_reason": string, "selection_reason": string }`
- `why_you_will_love_this.highlights`: at least 1 item
- `trip_description.included`: at least 1 item
- `trip_details.trip_type`: at least 1 item
- `daily_itinerary`: exactly wizard `trip.duration` days; each day at least 1 activity
- `trip_details.duration.days` must equal wizard duration; `nights` = days - 1
- Meals live inside `activities` (with times); swaps live in `activity_alternatives`
- `Essential Travel Tips` may be serialized as `essential_travel_tips` — either key is accepted by the API
- All money strings use JOD

## Money & content conventions
- Every money value is a string in JOD, written one of four ways:
  - confirmed price from the evidence → `"7 JOD"`
  - price derived from `pricing_level` → `"~10 JOD (estimated)"`
  - no cost at all → `"Free"`
  - genuinely unknowable → `"Not Available"`
- `activities[].estimated_cost` is always the **total for the whole party**, so the budget is a
  plain sum of the itinerary. A per-person figure belongs in `smart_tip`, never in the amount.
- `budget_summary.items[]` categories reflect what the trip actually contains — typically
  Accommodation, Meals, Activities & Entry Fees — plus a line comparing the total to the
  traveler's budget. Put estimation assumptions in that item's `notes`.
- Each category equals the matching itinerary lines added up. A price stated in a day and
  missing from the budget, or the reverse, is a contradiction.
- `total_estimated_cost` must equal the sum of the listed items and is never inflated toward
  the traveler's budget.
- `trip_details.number_of_travelers` is `adults + children + seniors` as a plain number
  string, and `trip_type` carries 2–4 labels drawn from group type and interests. Neither is
  ever left blank — both are given by the wizard, not judgement calls.
- `trip_details.budget.amount` is the bare number; the unit lives in `currency`.
- No event may appear in `daily_itinerary` or `activity_alternatives`; the itinerary is built
  from POIs, restaurants, and hotels only.
- No transportation activities, transfer legs, or travel-time claims anywhere.
- `activity_alternatives[].alternative_activity` must be a different real place from the same
  day's evidence — never a repeat of `original_activity`.
