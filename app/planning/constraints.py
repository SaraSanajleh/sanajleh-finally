"""Hard-constraint helpers for must-visit and places-to-avoid."""

from __future__ import annotations

from typing import Any

from app.planning.geo import region_key, text_mentions_region, wizard_region_keys
from app.planning.profile import TouristProfile


def avoid_tokens(profile: TouristProfile) -> list[str]:
    return [token.lower() for token in profile.places_to_avoid if token.strip()]


def item_is_avoided(name: str, region: str, extra: str, profile: TouristProfile) -> bool:
    hay = " ".join([name or "", region or "", extra or ""]).lower()
    return any(token in hay for token in avoid_tokens(profile))


def must_visit_satisfied(must_item: str, names: list[str], regions: list[str]) -> bool:
    target = region_key(must_item)
    aliases = wizard_region_keys([must_item])
    blob = " ".join(names + regions).lower()
    if target and target in blob:
        return True
    return text_mentions_region(blob, aliases)


def evaluate_constraints(
    profile: TouristProfile,
    scheduled_names: list[str],
    scheduled_regions: list[str],
) -> dict[str, Any]:
    unmet: list[dict[str, str]] = []
    for item in profile.must_visit:
        if not must_visit_satisfied(item, scheduled_names, scheduled_regions):
            unmet.append(
                {
                    "item": item,
                    "reason": "Geographic/time conflict or no grounded match in retrieved knowledge",
                    "reason_code": "must_visit_unmet",
                }
            )
    if not unmet:
        status = "satisfied"
    elif len(unmet) < len(profile.must_visit):
        status = "partially_satisfied"
    else:
        status = "unsatisfied" if profile.must_visit else "satisfied"
    if not profile.must_visit:
        status = "satisfied"
    return {"status": status, "unmet": unmet}
