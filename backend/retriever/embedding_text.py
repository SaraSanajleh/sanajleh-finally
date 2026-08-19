"""
ReTour Retriever — Station B2: Embedding-Text Builder
=====================================================

Purpose:
    Turn a (normalized) entity into the two texts the hybrid index needs:
      - dense_text : focused, meaning-carrying sentence -> dense vector.
      - sparse_text: wide net over ALL textual layers -> BM25 index.

Why two texts (Decision 2, revised):
    A single dense vector averages long text and drowns strong signals.
    We instead split the work across the two hybrid channels:
      * dense  -> concept/vibe matching ("quiet historic place for family").
      * sparse -> exact rare terms a user may type ("WiFi", "sunset", "4x4"),
                  captured wherever they live (notes, context, highlights...).
    This way no field is wasted, with no multi-vector complexity.

Design rules implemented:
    - Operational numbers (hours, price, duration, coordinates) NEVER enter
      either text — they are noise for matching, returned separately instead.
    - Empty (null / []) fields are silently skipped (unlike the response,
      where null is explicit).
    - Field set varies by entity_type; identity + semantic layers are shared.
"""

from typing import Tuple

# ---------------------------------------------------------------------
# Field maps per entity_type.
#   DENSE = focused: identity + semantic + vibe/taste fields only.
#   SPARSE_EXTRA = extra textual layers added ONLY to the BM25 net
#                  (notes, context, amenities...) — never to dense.
# Dotted paths are resolved against the entity dict.
# ---------------------------------------------------------------------

# Shared across all types (prefix + identity/theme layer).
_PREFIX = ["entity_type", "identity.category", "identity.subcategory",
           "location.region", "identity.name"]
_SEMANTIC = ["semantic.summary", "semantic.description", "semantic.themes",
             "semantic.tags", "semantic.keywords", "semantic.aliases"]

# Per-type vibe/taste fields for the DENSE text.
_DENSE_VIBE = {
    "poi": ["experience.experience_type", "experience.activity_level",
            "experience.best_visit_time", "experience.best_season",
            "experience.highlights", "audience.suitable_for"],
    "restaurant": ["experience.cuisine_types", "experience.meal_types",
                   "experience.service_style", "experience.atmosphere",
                   "experience.signature_dishes", "experience.best_visit_time",
                   "audience.suitable_for", "audience.occasion_suitability"],
    "hotel": ["experience.room_types", "experience.view_types",
              "experience.best_for", "experience.amenities",
              "audience.suitable_for"],
    "event": ["experience.highlights", "experience.indoor_outdoor",
              "audience.suitable_for", "operation.typical_months"],
}

# Per-type EXTRA textual layers, added to SPARSE only (wide BM25 net).
_SPARSE_EXTRA = {
    "poi": ["experience.facilities", "context.required_items", "context.notes"],
    "restaurant": ["experience.facilities", "context.dress_code", "context.notes"],
    "hotel": ["experience.facilities", "context.pet_policy",
              "context.check_in_requirements", "context.notes"],
    "event": ["experience.facilities", "context.weather_dependency",
              "context.dress_code", "context.notes"],
}


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _resolve(entity: dict, path: str):
    """Resolve a dotted path; return None if any hop is missing."""
    cur = entity
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _flatten(value) -> str:
    """Turn a field value into clean text; empty -> '' (skipped by caller)."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        parts = [_flatten(v) for v in value]
        return ", ".join(p for p in parts if p)
    if isinstance(value, (int, float)):
        return str(value)
    return ""


def _collect(entity: dict, paths) -> list:
    """Collect non-empty flattened values for a list of paths, in order."""
    out = []
    for p in paths:
        text = _flatten(_resolve(entity, p))
        if text:
            out.append(text)
    return out


# ---------------------------------------------------------------------
# API
# ---------------------------------------------------------------------

def build_texts(entity: dict) -> Tuple[str, str]:
    """Build (dense_text, sparse_text) for one entity.

    dense_text  = prefix + semantic + per-type vibe   (focused).
    sparse_text = dense_text + per-type extra layers   (wide BM25 net).
    """
    etype = entity.get("entity_type", "")
    vibe = _DENSE_VIBE.get(etype, [])
    extra = _SPARSE_EXTRA.get(etype, [])

    dense_parts = _collect(entity, _PREFIX + _SEMANTIC + vibe)
    dense_text = " | ".join(dense_parts)

    # sparse = everything in dense + the extra textual layers
    sparse_parts = dense_parts + _collect(entity, extra)
    sparse_text = " | ".join(sparse_parts)

    return dense_text, sparse_text


# ---------------------------------------------------------------------
# Self-check
# ---------------------------------------------------------------------
if __name__ == "__main__":
    poi = {
        "entity_type": "poi",
        "identity": {"name": "The Treasury", "category": "UNESCO",
                     "subcategory": "Archaeological Site"},
        "semantic": {"summary": "Rock-cut Nabataean temple in Petra.",
                     "description": "Carved into the sandstone cliff.",
                     "themes": ["History", "Archaeology"],
                     "tags": ["petra"], "keywords": ["treasury"],
                     "aliases": ["Al-Khazneh"]},
        "location": {"region": "Ma'an Governorate",
                     "coordinates": {"latitude": 30.32, "longitude": 35.45}},
        "operation": {"opening_hours": "06:00", "average_visit_minutes": 45},
        "pricing": {"entry_fee": 50, "currency": "JOD"},
        "audience": {"suitable_for": ["Family"], "accessibility": ["Elderly Friendly"]},
        "experience": {"experience_type": ["Sightseeing"], "activity_level": "Medium",
                       "best_visit_time": ["Morning"], "highlights": ["Carved by Nabataeans"],
                       "facilities": []},
        "context": {"required_items": ["Water"], "notes": "One-day ticket. Camel rides available."},
    }
    dense, sparse = build_texts(poi)

    # dense must carry meaning, must NOT carry operational numbers
    assert "The Treasury" in dense and "History" in dense
    assert "50" not in dense and "06:00" not in dense and "45" not in dense
    # sparse must additionally carry the wide layers (notes/required_items)
    assert "Camel rides" in sparse and "Water" in sparse
    assert "Camel rides" not in dense  # notes are sparse-only
    # sparse is a superset of dense
    assert dense in sparse

    print("dense :", dense)
    print("sparse:", sparse)
    print("All checks passed — embedding-text builder works correctly.")
