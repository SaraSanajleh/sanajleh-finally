"""Helpers to finish multi-day itineraries when small models stop after day 1."""

from __future__ import annotations

import json
from typing import Any

from app.schemas.response.package_response import ItineraryDay, TourismPackage
from app.validators.json_parser import extract_json_object
from app.validators.package_response_validator import normalize_package_payload


def day_array_skeleton(days: int) -> str:
    """Literal day slots the model must fill (recency bias for small LLMs)."""
    slots = [
        "{"
        f'"day_number":"{i}",'
        '"day_title":"...",'
        '"day_summary":"...",'
        '"activities":[{"start_time":"...","end_time":"...","activity_title":"...",'
        '"description":"...","location":"...","estimated_cost":"...","smart_tip":"..."}],'
        '"activity_alternatives":[{"original_activity":"...","alternative_activity":"...",'
        '"reason":"..."}]'
        "}"
        for i in range(1, days + 1)
    ]
    return "[\n  " + ",\n  ".join(slots) + "\n]"


_BLANK_MARKERS = {"", "...", "…", "n/a", "na", "todo", "tbd", "placeholder"}


def _is_blank(value: str | None) -> bool:
    return (value or "").strip().lower() in _BLANK_MARKERS


def day_is_incomplete(day: ItineraryDay) -> bool:
    """True for missing content or skeleton placeholders left unfilled."""
    if _is_blank(day.day_title) or _is_blank(day.day_summary):
        return True
    if not day.activities:
        return True
    for act in day.activities:
        if _is_blank(act.activity_title) or _is_blank(act.location):
            return True
    return False


def missing_day_numbers(package: TourismPackage, expected_days: int) -> list[str]:
    present = {str(d.day_number).strip() for d in package.daily_itinerary}
    return [str(i) for i in range(1, expected_days + 1) if str(i) not in present]


def days_needing_fill(package: TourismPackage, expected_days: int) -> list[str]:
    """Missing day numbers plus days that exist but are empty templates."""
    needed = set(missing_day_numbers(package, expected_days))
    for day in package.daily_itinerary:
        key = str(day.day_number).strip()
        if key and day_is_incomplete(day):
            needed.add(key)
    return sorted(needed, key=lambda x: int(x) if x.isdigit() else 0)


def merge_itinerary_days(
    package: TourismPackage,
    extra_days: list[ItineraryDay],
    expected_days: int,
) -> TourismPackage:
    """Merge extra days into package and normalize duration fields."""
    by_num: dict[str, ItineraryDay] = {}
    for day in package.daily_itinerary:
        key = str(day.day_number).strip()
        if key:
            by_num[key] = day
    for day in extra_days:
        key = str(day.day_number).strip()
        if key:
            by_num[key] = day

    ordered: list[dict[str, Any]] = []
    for i in range(1, expected_days + 1):
        key = str(i)
        if key not in by_num:
            raise ValueError(f"missing day_number {key} after merge")
        ordered.append(by_num[key].model_dump(mode="python"))

    data = package.model_dump(mode="python")
    data["daily_itinerary"] = ordered
    details = data.setdefault("trip_details", {})
    duration = details.setdefault("duration", {})
    duration["days"] = str(expected_days)
    duration["nights"] = str(max(expected_days - 1, 0))
    return TourismPackage.model_validate(data)


def parse_itinerary_days_payload(raw_text: str) -> list[ItineraryDay]:
    """Parse a completion response that is either a day list or a package fragment."""
    payload = extract_json_object(raw_text)
    if isinstance(payload, list):
        days_raw = payload
    elif isinstance(payload, dict):
        payload = normalize_package_payload(payload)
        days_raw = payload.get("daily_itinerary")
        if days_raw is None and isinstance(payload.get("day_number"), (str, int)):
            days_raw = [payload]
    else:
        raise ValueError("completion JSON must be object or array")

    if not isinstance(days_raw, list) or not days_raw:
        raise ValueError("completion JSON missing daily_itinerary days")

    return [ItineraryDay.model_validate(item) for item in days_raw]


def stub_package_from_days(days: list[ItineraryDay], expected_days: int) -> TourismPackage:
    """Minimal package wrapper so day-completion helpers can run on phase-1 output."""
    return TourismPackage.model_validate(
        {
            "daily_itinerary": [d.model_dump(mode="python") for d in days],
            "trip_details": {
                "duration": {
                    "days": str(expected_days),
                    "nights": str(max(expected_days - 1, 0)),
                }
            },
        }
    )


def attach_locked_itinerary(
    shell: TourismPackage,
    locked_days: list[ItineraryDay],
    expected_days: int,
) -> TourismPackage:
    """Force locked itinerary into a shell package."""
    data = shell.model_dump(mode="python")
    data["daily_itinerary"] = [d.model_dump(mode="python") for d in locked_days]
    details = data.setdefault("trip_details", {})
    duration = details.setdefault("duration", {})
    duration["days"] = str(expected_days)
    duration["nights"] = str(max(expected_days - 1, 0))
    return TourismPackage.model_validate(data)


def tokens_for_itinerary_phase(days: int, cap: int) -> int:
    """Cloud-friendly itinerary budget (gpt-oss may spend some tokens on thinking)."""
    return min(cap, max(2500, 900 * days + 800))


def tokens_for_narrative_phase(days: int, cap: int) -> int:
    return min(cap, max(1800, 1200 + 120 * days))


def tokens_for_synthesis_phase(days: int, cap: int) -> int:
    return min(cap, max(1800, 1200 + 120 * days))


# Backward-compatible alias used by older tests / scripts.
def tokens_for_shell_phase(days: int, cap: int) -> int:
    return tokens_for_narrative_phase(days, cap)


def build_missing_days_prompt(
    *,
    expected_days: int,
    package: TourismPackage,
    missing: list[str],
    knowledge: dict[str, Any],
) -> str:
    existing = [
        {
            "day_number": d.day_number,
            "day_title": d.day_title,
            "locations": [a.location for a in (d.activities or []) if a.location],
        }
        for d in package.daily_itinerary
    ]
    clusters = list(knowledge.get("clusters") or [])
    used = min(len(existing), len(clusters))
    remaining_clusters = clusters[used:] or clusters
    kn_slim = {
        "duration_days": expected_days,
        "clusters": remaining_clusters,
        "meta": (knowledge.get("meta") or {}),
    }
    return (
        f"You returned an itinerary with only {len(package.daily_itinerary)} day(s). "
        f"The trip needs exactly {expected_days} days.\n"
        f"Emit ONLY a JSON object with the MISSING days "
        f"(day_number {', '.join(missing)}). No markdown. No other top-level keys.\n\n"
        f"Required shape:\n"
        f'{{"daily_itinerary":[ /* only missing days */ ]}}\n\n'
        f"Existing days (do NOT repeat places/themes):\n"
        f"{json.dumps(existing, ensure_ascii=False)}\n\n"
        f"Use these retrieved clusters for the missing days:\n"
        f"{json.dumps(kn_slim, ensure_ascii=False)}\n\n"
        "Rules: short text; include attractions + meal activities with start_time/end_time; "
        "names MUST match EntityCard names from the clusters; omit transportation."
    )
