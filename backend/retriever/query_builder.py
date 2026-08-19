"""
ReTour Retriever — Station B5.5: Query Builder
==============================================

Turns the raw wizard (25 fields) into what the engine consumes:
    build_query(wizard) -> {
        "prefs": { query_text, hard fields, ranking fields, planning fields },
        "meta":  { unsupported, places_to_avoid, deferred },
        "duration": int,
    }

Design decisions:
  - Deterministic template INSIDE Beta (reproducibility): the same wizard
    always yields the same query_text — the agent does not send free query text.
  - query_text is built from the SAME vocabulary as the entity dense_text (B2),
    so dense matching aligns (semantic fields -> semantic sentence).
  - Field routing follows Decision 1 (field policy): semantic -> query_text,
    hard/ranking -> prefs, unsupported/free -> meta.

CRITICAL — key names in `prefs` must match exactly what retrieval.py expects:
    accessibilityNeeds -> accessibility | cuisine_diet -> dietary_options
    groupType -> suitable_for | query_text
"""

from typing import Dict, Any, List

# dietary values live in wizard `cuisine`; the rest of cuisine are cuisines
_DIET_VALUES = {"Halal", "Vegetarian", "Vegan"}

# wizard accessibility values that HAVE a knowledge counterpart (hard filter);
# the others are unsupported -> meta
_SUPPORTED_ACCESS = {"Wheelchair Access", "Elder Friendly"}

# semantic wizard fields that feed query_text (order = template, deterministic)
# smePreferences has NO knowledge counterpart -> semantic channel is the only way
# it can influence retrieval at all (so it is not silently dropped).
_SEMANTIC_ORDER = [
    "groupType", "specialOccasion", "interests", "freeText",
    "tripPace", "activityLevel", "aiPriority", "smePreferences",
]


def _as_list(v) -> List[str]:
    if v is None or v == "":
        return []
    return v if isinstance(v, list) else [v]


def _parse_duration(wizard: Dict[str, Any]) -> int:
    """duration is '1'|'2'|'3'|'5'|'7'|'Custom'; Custom -> customDuration.
    Always returns a positive int (engine uses K = 4*duration + 8)."""
    d = wizard.get("duration", "")
    if d == "Custom":
        d = wizard.get("customDuration", "")
    try:
        n = int(str(d).strip())
        return n if n > 0 else 1
    except (ValueError, TypeError):
        return 1


def _build_query_text(wizard: Dict[str, Any]) -> str:
    """Deterministic semantic sentence from the wizard's semantic fields,
    in a fixed order. Empty fields are skipped silently."""
    parts: List[str] = []
    for field in _SEMANTIC_ORDER:
        val = wizard.get(field)
        if field == "groupType" and val:
            parts.append(f"{val} trip")
        elif field == "interests":
            parts.extend(_as_list(val))
        else:
            parts.extend(_as_list(val))
    # drop no-preference noise
    cleaned = [p for p in parts if p and p not in
               ("No Preference", "None", "no_pref")]
    return ", ".join(cleaned)


def build_query(wizard: Dict[str, Any]) -> Dict[str, Any]:
    """Main entry: wizard -> {prefs, meta, duration}."""
    # --- split cuisine into diet (hard) vs cuisines (ranking) ---
    cuisine_all = _as_list(wizard.get("cuisine"))
    diet = [c for c in cuisine_all if c in _DIET_VALUES]
    cuisines = [c for c in cuisine_all if c not in _DIET_VALUES]

    # --- split accessibility into supported (hard) vs unsupported (meta) ---
    access_all = _as_list(wizard.get("accessibilityNeeds"))
    access_hard = [a for a in access_all if a in _SUPPORTED_ACCESS]
    access_unsupported = [a for a in access_all if a not in _SUPPORTED_ACCESS]

    # --- prefs: exactly the keys the engine expects ---
    prefs: Dict[str, Any] = {
        "query_text": _build_query_text(wizard),
        # HARD (engine _HARD_MAP keys)
        "accessibilityNeeds": access_hard,      # -> accessibility
        "cuisine_diet": diet,                    # -> dietary_options
        "groupType": wizard.get("groupType"),    # -> suitable_for
        # ranking / boost (used by ranking layer / structured)
        "mustVisit": _as_list(wizard.get("mustVisit")),
        "preferredRegion": _as_list(wizard.get("preferredRegion")),
        # explicit user terms -> literal-match boost (user wrote it => must surface)
        "interests": _as_list(wizard.get("interests")),
        "freeText": wizard.get("freeText", "") or "",
        "hotelRating": wizard.get("hotelRating"),
        "accommodationType": wizard.get("accommodationType"),
        "cuisines": cuisines,
        "specialOccasion": wizard.get("specialOccasion"),
        "activityLevel": wizard.get("activityLevel"),
        # placesToAvoid also lives in meta (honesty channel); mirrored here so the
        # engine can apply it as a REAL exclusion, not just report it.
        "placesToAvoid": wizard.get("placesToAvoid", "") or "",
        # planning (passed through to the response; agent computes)
        "startDate": wizard.get("startDate"),
        "totalBudget": wizard.get("totalBudget"),
        "adults": wizard.get("adults"),
        "children": wizard.get("children"),
        "seniors": wizard.get("seniors"),
        "tripPace": wizard.get("tripPace"),
        "aiPriority": wizard.get("aiPriority"),
    }

    # --- meta: honesty channel (not filter, not rank) ---
    meta: Dict[str, Any] = {
        "unsupported": access_unsupported,
        "places_to_avoid": wizard.get("placesToAvoid", "") or "",
        "deferred": {
            "preferredLanguage": wizard.get("preferredLanguage"),
            "smePreferences": _as_list(wizard.get("smePreferences")),
        },
    }

    return {"prefs": prefs, "meta": meta, "duration": _parse_duration(wizard)}


# ---------------------------------------------------------------------
# Self-check
# ---------------------------------------------------------------------
if __name__ == "__main__":
    wizard = {
        "startDate": "2025-08-15", "duration": "5", "customDuration": "",
        "arrivalAirport": "AMM", "totalBudget": 1500,
        "preferredRegion": ["Petra", "Wadi Rum"],
        "adults": 2, "children": 1, "childrenAges": ["8"], "seniors": 0,
        "groupType": "family",
        "accessibilityNeeds": ["Wheelchair Access", "Visual Assistance"],
        "interests": ["history", "hiking"],
        "tripPace": "Balanced", "activityLevel": "Moderate",
        "mustVisit": ["Petra"], "placesToAvoid": "crowded malls",
        "accommodationType": "hotel", "hotelRating": "4 star",
        "cuisine": ["Local Jordanian", "Halal", "Vegan"],
        "specialOccasion": "None", "smePreferences": [],
        "aiPriority": "authentic", "freeText": "sunset dinner please",
    }
    out = build_query(wizard)
    p, m = out["prefs"], out["meta"]

    # duration parsed to int
    assert out["duration"] == 5

    # query_text carries semantic fields, in template order, no operational data
    qt = p["query_text"]
    assert "family trip" in qt and "history" in qt and "hiking" in qt
    assert "sunset dinner please" in qt and "authentic" in qt
    assert "1500" not in qt and "Petra" not in qt  # region/budget are not semantic text

    # cuisine split: diet -> hard, cuisines -> ranking
    assert p["cuisine_diet"] == ["Halal", "Vegan"]
    assert p["cuisines"] == ["Local Jordanian"]

    # accessibility split: supported -> hard, unsupported -> meta
    assert p["accessibilityNeeds"] == ["Wheelchair Access"]
    assert m["unsupported"] == ["Visual Assistance"]

    # engine-expected keys present with exact names
    for key in ("query_text", "accessibilityNeeds", "cuisine_diet", "groupType"):
        assert key in p, key

    # meta honesty
    assert m["places_to_avoid"] == "crowded malls"

    print("All checks passed — query builder works correctly.")