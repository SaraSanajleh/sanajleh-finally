"""
ReTour Retriever — Station B1: Normalization Layer
==================================================

Purpose:
    Bridge the vocabulary mismatch between wizard values and knowledge-base
    values (same meaning, different spelling). Without this, hard filters
    fail silently — e.g. wizard "Elder Friendly" vs data "Elderly Friendly"
    would drop a valid entity.

Design decision implemented:
    Decision 1 (Field Policy) — "best-match via normalize, for closed enums
    only, never free text."

Source of tables:
    Allowed-value lists inside the Gemini generation prompts + wizard enums.
    (Not guessed — derived from the same source that generates the data.)

Runs in two places, with the same table:
    1. Ingestion time → on entity values, before indexing.
    2. Request time   → on wizard values, before the hard filter.
"""

from typing import Optional

# ---------------------------------------------------------------------
# Alias tables — one per hard-filter field.
# key   = possible spelling (lowercased)
# value = canonical spelling (knowledge-base form; wizard is mapped to it)
# ---------------------------------------------------------------------

# accessibility — canonical values in the knowledge base:
#   Wheelchair Accessible, Elevator, Stroller Friendly, Elderly Friendly,
#   Parking, Public Transport, Pet Friendly
# Wizard sends: Wheelchair Access, Elder Friendly
# (Visual / Hearing / Limited Walking have no counterpart -> handled as meta)
_ACCESSIBILITY = {
    "wheelchair access": "Wheelchair Accessible",
    "wheelchair accessible": "Wheelchair Accessible",
    "elder friendly": "Elderly Friendly",
    "elderly friendly": "Elderly Friendly",
}

# dietary_options — canonical: Halal, Vegetarian, Vegan, Gluten-Free,
#                              No Special Options
# Wizard sends Halal / Vegetarian / Vegan — identical, we just unify casing.
_DIETARY = {
    "halal": "Halal",
    "vegetarian": "Vegetarian",
    "vegan": "Vegan",
    "gluten-free": "Gluten-Free",
    "no special options": "No Special Options",
}

# cuisine_types — canonical: Jordanian, Levantine, Middle Eastern,
#   Mediterranean, Italian, Asian, Indian, International, Seafood,
#   Vegetarian/Vegan, Fast Food, Cafe/Desserts
# Wizard sends "Local Jordanian" -> "Jordanian"; rest align directly.
_CUISINE = {
    "local jordanian": "Jordanian",
    "jordanian": "Jordanian",
    "middle eastern": "Middle Eastern",
    "international": "International",
    "seafood": "Seafood",
    "levantine": "Levantine",
    "mediterranean": "Mediterranean",
    "italian": "Italian",
    "asian": "Asian",
    "indian": "Indian",
    "fast food": "Fast Food",
    "cafe/desserts": "Cafe/Desserts",
    "vegetarian/vegan": "Vegetarian/Vegan",
}

# suitable_for (groupType) — canonical: Family, Couples, Solo, Friends,
#   Groups, Business, Honeymoon, Students, Seniors, Children
# Wizard sends lowercase/singular: solo, couple, family, friends, business
_GROUP_TYPE = {
    "solo": "Solo",
    "couple": "Couples",
    "couples": "Couples",
    "family": "Family",
    "friends": "Friends",
    "business": "Business",
    "honeymoon": "Honeymoon",
    "students": "Students",
    "seniors": "Seniors",
    "children": "Children",
    "groups": "Groups",
}

# field -> its alias table
_TABLES = {
    "accessibility": _ACCESSIBILITY,
    "dietary_options": _DIETARY,
    "cuisine_types": _CUISINE,
    "suitable_for": _GROUP_TYPE,
}

# Critical list-fields normalized on the entity at ingestion time.
_ENTITY_LIST_FIELDS_IN_AUDIENCE = ("accessibility", "dietary_options", "suitable_for")
_ENTITY_LIST_FIELDS_IN_EXPERIENCE = ("cuisine_types",)


# ---------------------------------------------------------------------
# API
# ---------------------------------------------------------------------

def normalize(field: str, value: str) -> Optional[str]:
    """Normalize a single value for a known field.

    - Unknown field  -> value returned unchanged (e.g. free text passes through).
    - Unknown value  -> value returned unchanged (never invents).
    - Matching is case-insensitive on the key.
    """
    if value is None:
        return None
    table = _TABLES.get(field)
    if table is None:
        return value  # field not subject to normalization -> pass through
    return table.get(value.strip().lower(), value)


def normalize_list(field: str, values) -> list:
    """Normalize a list of values; dedupe while preserving order."""
    if not values:
        return values if values is not None else []
    seen, out = set(), []
    for v in values:
        nv = normalize(field, v)
        if nv not in seen:
            seen.add(nv)
            out.append(nv)
    return out


def normalize_entity(entity: dict) -> dict:
    """Normalize an entity's critical fields at ingestion time (on a copy).

    Touches only: audience.{accessibility, dietary_options, suitable_for}
                  experience.cuisine_types
    Leaves untouched: region (ranking), free text, everything else.
    """
    e = dict(entity)  # shallow copy — don't mutate the original

    aud = e.get("audience")
    if isinstance(aud, dict):
        aud = dict(aud)
        for f in _ENTITY_LIST_FIELDS_IN_AUDIENCE:
            if f in aud:
                aud[f] = normalize_list(f, aud[f])
        e["audience"] = aud

    exp = e.get("experience")
    if isinstance(exp, dict):
        exp = dict(exp)
        for f in _ENTITY_LIST_FIELDS_IN_EXPERIENCE:
            if f in exp:
                exp[f] = normalize_list(f, exp[f])
        e["experience"] = exp

    return e


def normalize_wizard_value(field: str, value):
    """Normalize a wizard value (single or list) at request time,
    before the hard filter."""
    if isinstance(value, list):
        return normalize_list(field, value)
    return normalize(field, value)


def region_key(region: str) -> str:
    """Canonical region key.

    Collapses the 'Amman' vs 'Amman Governorate' spelling drift that appears
    ACROSS entity types in the data (POIs/restaurants say 'X Governorate';
    hotels/events often say just 'X'). Used to join cluster-level hotels/events
    to a day's anchor region reliably, and as a stable region match key.

        'Amman Governorate' -> 'amman'
        'Ajloun'            -> 'ajloun'
        "Ma'an Governorate" -> "ma'an"
    """
    if not region:
        return ""
    r = str(region).strip().lower()
    if r.endswith("governorate"):
        r = r[:-len("governorate")].strip()
    return r


# ---------------------------------------------------------------------
# Self-check (runs only when executed directly)
# ---------------------------------------------------------------------
if __name__ == "__main__":
    # Known mappings
    assert normalize("accessibility", "Wheelchair Access") == "Wheelchair Accessible"
    assert normalize("accessibility", "Elder Friendly") == "Elderly Friendly"
    assert normalize("cuisine_types", "Local Jordanian") == "Jordanian"
    assert normalize("suitable_for", "couple") == "Couples"
    assert normalize("dietary_options", "halal") == "Halal"
    # No alias -> passes through unchanged
    assert normalize("accessibility", "Parking") == "Parking"
    # Non-normalized field -> passes through
    assert normalize("region", "Ma'an Governorate") == "Ma'an Governorate"

    # Full entity
    sample = {
        "audience": {
            "accessibility": ["Wheelchair Access", "Elder Friendly"],
            "dietary_options": ["halal", "Vegan"],
            "suitable_for": ["family", "couple"],
        },
        "experience": {"cuisine_types": ["Local Jordanian", "Seafood"]},
    }
    out = normalize_entity(sample)
    assert out["audience"]["accessibility"] == ["Wheelchair Accessible", "Elderly Friendly"]
    assert out["audience"]["suitable_for"] == ["Family", "Couples"]
    assert out["experience"]["cuisine_types"] == ["Jordanian", "Seafood"]

    print("All checks passed — normalization layer works correctly.")