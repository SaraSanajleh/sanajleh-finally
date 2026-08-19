"""Schema + business-rule validation for TourismPackage output."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from app.core.exceptions import LLMResponseParseError, ValidationError as ReTourValidationError
from app.planning.constraints import evaluate_constraints, item_is_avoided
from app.planning.profile import TouristProfile
from app.retrieval.knowledge import RetrievedKnowledge
from app.schemas.response.package_response import (
    PackageWarning,
    TourismPackage,
)
from app.planning.itinerary import sme_payload
from app.sme.models import SMEMatch, SMERecord
from app.validators.json_parser import extract_json_object


DATASET_FOR_TYPE = {
    "poi": "pois",
    "restaurant": "restaurants",
    "hotel": "hotels",
    "activity": "pois",
}


def parse_package_json(raw: str) -> dict[str, Any]:
    payload = extract_json_object(raw)
    if not isinstance(payload, dict):
        raise LLMResponseParseError("LLM did not return a JSON object")
    if "days" not in payload and isinstance(payload.get("daily_itinerary"), list):
        payload["days"] = _legacy_days(payload["daily_itinerary"])
    if "trip" not in payload:
        payload["trip"] = {
            "title": payload.get("trip_title") or "",
            "summary": "",
        }
    payload["warnings"] = _normalize_warnings(payload.get("warnings"))
    payload["sources"] = _normalize_sources(payload.get("sources"))
    return payload


def _normalize_warnings(raw: object) -> list[dict[str, str]]:
    if not raw:
        return []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            out.append({"code": "note", "message": item.strip(), "severity": "info"})
            continue
        if not isinstance(item, dict):
            continue
        message = str(item.get("message") or item.get("text") or item.get("warning") or "").strip()
        if not message:
            continue
        out.append(
            {
                "code": str(item.get("code") or "note"),
                "message": message,
                "severity": str(item.get("severity") or "info"),
            }
        )
    return out


def _normalize_sources(raw: object) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "dataset": str(item.get("dataset") or "unknown"),
                "record_id": str(item.get("record_id") or item.get("id") or "unknown"),
            }
        )
    return out


def _legacy_days(rows: list[Any]) -> list[dict[str, Any]]:
    days: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        schedule = []
        for act in row.get("activities") or []:
            if not isinstance(act, dict):
                continue
            schedule.append(
                {
                    "time": act.get("start_time") or "",
                    "end_time": act.get("end_time") or "",
                    "type": "activity",
                    "name": act.get("activity_title") or act.get("name") or "",
                    "location": act.get("location") or "",
                    "description": act.get("description") or "",
                    "estimated_cost": act.get("estimated_cost") or "not_available",
                    "reason": act.get("smart_tip") or "",
                }
            )
        days.append(
            {
                "day": idx,
                "theme": row.get("day_title") or "",
                "summary": row.get("day_summary") or "",
                "schedule": schedule,
                "smes": [],
            }
        )
    return days


def validate_schema(payload: dict[str, Any]) -> TourismPackage:
    try:
        return TourismPackage.model_validate(payload)
    except ValidationError as exc:
        raise ReTourValidationError(
            f"Tourism package failed schema validation: {exc}"
        ) from exc


def apply_profile_facts(package: TourismPackage, profile: TouristProfile) -> TourismPackage:
    data = package.model_dump(mode="python")
    trip = data.get("trip") or {}
    trip["start_date"] = profile.start_date.isoformat()
    trip["end_date"] = profile.end_date.isoformat()
    trip["duration_days"] = profile.duration_days
    trip["nights"] = profile.nights
    trip["arrival_airport"] = profile.arrival_airport
    trip["language"] = profile.preferred_language
    if not trip.get("regions"):
        trip["regions"] = list(profile.preferred_regions or profile.must_visit)
    data["trip"] = trip
    data["trip_title"] = data.get("trip_title") or trip.get("title") or "Jordan journey"
    trip["title"] = trip.get("title") or data["trip_title"]
    data["traveler_profile"] = {
        "group_type": profile.group_type,
        "adults": profile.adults,
        "children": profile.children,
        "children_ages": profile.children_ages,
        "seniors": profile.seniors,
        "total_travelers": profile.total_travelers,
        "interests": profile.interests,
        "pace": profile.trip_pace,
        "activity_level": profile.activity_level,
        "accessibility_needs": profile.accessibility_needs,
    }
    budget = data.get("budget") or {}
    budget["traveler_budget"] = profile.total_budget
    budget["currency"] = "JOD"
    data["budget"] = budget
    if not data.get("package_id"):
        data["package_id"] = f"pkg-{uuid4().hex[:12]}"
    return TourismPackage.model_validate(data)


def ground_and_repair(
    package: TourismPackage,
    profile: TouristProfile,
    knowledge: RetrievedKnowledge,
    sme_index: dict[str, SMERecord],
    sme_matches: list[SMEMatch],
) -> tuple[TourismPackage, list[str]]:
    errors: list[str] = []
    catalog = knowledge.id_index()
    match_by_id = {m.record.sme_id: m for m in sme_matches}
    data = package.model_dump(mode="python")
    warnings = list(data.get("warnings") or [])
    sources: list[dict[str, str]] = []
    used_ids: set[str] = set()
    scheduled_names: list[str] = []
    scheduled_regions: list[str] = []

    days = list(data.get("days") or [])
    if len(days) != profile.duration_days:
        errors.append(f"Expected {profile.duration_days} days, received {len(days)}")
        days = _resize_days(days, profile)

    for index, day in enumerate(days):
        day["day"] = index + 1
        day["date"] = (profile.start_date + timedelta(days=index)).isoformat()
        kept_schedule = []
        for item in day.get("schedule") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            item_id = str(item.get("item_id") or "")
            region = str(item.get("location") or day.get("region") or "")
            if item_is_avoided(name, region, item_id, profile):
                warnings.append(
                    {
                        "code": "avoided_item_removed",
                        "message": f"Removed excluded place: {name or item_id}",
                        "severity": "warning",
                    }
                )
                continue
            card = catalog.get(item_id) or catalog.get(name.lower())
            if item.get("type") in {"poi", "restaurant", "hotel", "activity"}:
                if card is None:
                    warnings.append(
                        {
                            "code": "ungrounded_item_removed",
                            "message": f"Removed ungrounded item: {name or item_id}",
                            "severity": "warning",
                        }
                    )
                    continue
                if card.item_id in used_ids and item.get("type") != "hotel":
                    continue
                used_ids.add(card.item_id)
                item["item_id"] = card.item_id
                item["name"] = card.name
                item["location"] = item.get("location") or card.city or card.region
                if card.latitude is not None:
                    item["coordinates"] = {
                        "latitude": card.latitude,
                        "longitude": card.longitude,
                        "precision": card.geo_precision,
                    }
                dataset = DATASET_FOR_TYPE.get(item.get("type") or card.entity_type, card.entity_type)
                item["source"] = {"dataset": dataset, "record_id": card.item_id}
                sources.append(item["source"])
                scheduled_names.append(card.name)
                scheduled_regions.append(card.region)
            kept_schedule.append(item)
        day["schedule"] = kept_schedule

        day["smes"] = []
        days[index] = day

    data["days"] = days
    recommended = _ground_trip_smes(
        (data.get("sme_value") or {}).get("recommended") or [],
        sme_index,
        match_by_id,
        sme_matches,
        warnings,
        sources,
    )
    sme_value = data.get("sme_value") or {}
    sme_value["recommended"] = recommended
    sme_value.setdefault("headline", "Your guide and operator for this journey")
    sme_value.setdefault(
        "summary",
        "One local guide and one tour operator for the whole package.",
    )
    data["sme_value"] = sme_value
    constraint = evaluate_constraints(profile, scheduled_names, scheduled_regions)
    planning = data.get("planning") or {}
    planning["constraint_status"] = constraint
    planning["constraints"] = {
        "must_visit": profile.must_visit,
        "places_to_avoid": profile.places_to_avoid,
    }
    data["planning"] = planning
    data["status"] = "complete" if constraint["status"] == "satisfied" else "partial"
    data["warnings"] = _unique_warnings(warnings)
    data["sources"] = _unique_sources(sources)
    if not any(day.get("schedule") for day in days):
        errors.append("No grounded schedule items remain")
    package = TourismPackage.model_validate(data)
    return package, errors


def _ground_trip_smes(
    recommended: list[Any],
    sme_index: dict[str, SMERecord],
    match_by_id: dict[str, SMEMatch],
    sme_matches: list[SMEMatch],
    warnings: list[dict[str, str]],
    sources: list[dict[str, str]],
) -> list[dict[str, Any]]:
    grounded: list[dict[str, Any]] = []
    seen: set[str] = set()
    seen_types: set[str] = set()

    def _take(match: SMEMatch) -> None:
        if match.record.sme_id in seen or match.record.sme_type in seen_types:
            return
        payload = sme_payload(match)
        seen.add(match.record.sme_id)
        seen_types.add(match.record.sme_type)
        if payload.get("source"):
            sources.append(payload["source"])
        grounded.append(payload)

    for sme in recommended:
        if not isinstance(sme, dict):
            continue
        record = sme_index.get(str(sme.get("sme_id") or ""))
        if record is None:
            warnings.append(
                {
                    "code": "ungrounded_sme_removed",
                    "message": f"Removed unknown SME: {sme.get('name') or sme.get('sme_id')}",
                    "severity": "warning",
                }
            )
            continue
        match = match_by_id.get(record.sme_id)
        if match:
            _take(match)
        elif record.sme_type not in seen_types:
            fallback = SMEMatch(record=record, score=0.0, role=record.sme_type.replace("_", " ").title())
            _take(fallback)
    for match in sme_matches:
        _take(match)
        if len(grounded) >= 2:
            break
    return grounded[:2]


def _resize_days(days: list[dict[str, Any]], profile: TouristProfile) -> list[dict[str, Any]]:
    out = [day for day in days if isinstance(day, dict)]
    while len(out) < profile.duration_days:
        out.append({"day": len(out) + 1, "schedule": [], "smes": [], "theme": "", "summary": ""})
    return out[: profile.duration_days]


def _unique_warnings(rows: list[Any]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, PackageWarning):
            row = row.model_dump()
        if not isinstance(row, dict):
            continue
        key = f"{row.get('code')}:{row.get('message')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _unique_sources(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for row in rows:
        key = f"{row.get('dataset')}:{row.get('record_id')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def assert_package_ready(package: TourismPackage, profile: TouristProfile) -> None:
    if len(package.days) != profile.duration_days:
        raise ReTourValidationError(
            f"Package day count does not match trip duration: expected {profile.duration_days}, got {len(package.days)}"
        )
    if not any(day.schedule for day in package.days):
        raise ReTourValidationError("Package has no grounded itinerary items")
    if not package.trip_title and not package.trip.title:
        raise ReTourValidationError("Package is missing a title")
