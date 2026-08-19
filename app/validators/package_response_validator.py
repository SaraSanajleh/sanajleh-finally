"""Validate LLM output against the TourismPackage schema."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.core.exceptions import (
    LLMResponseParseError,
    ValidationError as ReTourValidationError,
)
from app.schemas.request.package_request import PackageRequest
from app.schemas.response.package_response import TourismPackage
from app.utils.logging import get_logger
from app.validators.json_parser import extract_json_object

logger = get_logger(__name__)

_KEY_ALIASES = {
    "daily itinerary": "daily_itinerary",
    "Daily Itinerary": "daily_itinerary",
    "itinerary": "daily_itinerary",
    "days": "daily_itinerary",
    "Essential Travel Tips": "essential_travel_tips",
    "essential travel tips": "essential_travel_tips",
    "travel_tips": "essential_travel_tips",
    "welcome message": "welcome_message",
    "trip title": "trip_title",
    "trip description": "trip_description",
    "trip details": "trip_details",
    "budget summary": "budget_summary",
    "why you will love this": "why_you_will_love_this",
}

NARRATIVE_KEYS = (
    "welcome_message",
    "why_you_will_love_this",
    "trip_title",
    "trip_description",
    "trip_details",
)

SYNTHESIS_KEYS = (
    "budget_summary",
    "essential_travel_tips",
    "explanations",
)


def _stringify_scalars(obj: Any) -> Any:
    """Coerce numeric scalars to strings where the package schema expects strings."""
    if isinstance(obj, dict):
        return {k: _stringify_scalars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_stringify_scalars(v) for v in obj]
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float)):
        return str(obj)
    return obj


_HOIST_FROM_TRIP_DESCRIPTION = (
    "daily_itinerary",
    "trip_details",
    "budget_summary",
    "essential_travel_tips",
    "Essential Travel Tips",
    "explanations",
    "why_you_will_love_this",
    "trip_title",
    "welcome_message",
)


def _hoist_nested_package_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """gpt-oss often nests package spine fields inside trip_description."""
    desc = payload.get("trip_description")
    if not isinstance(desc, dict):
        return payload

    # Also hoist when model used a wrong wrapper name for the narrative block.
    for nested_key in ("trip_description", "description", "package"):
        nested = desc.get(nested_key) if nested_key != "trip_description" else None
        if isinstance(nested, dict) and (
            "daily_itinerary" in nested or "budget_summary" in nested
        ):
            desc = {**desc, **nested}

    hoisted = False
    for key in _HOIST_FROM_TRIP_DESCRIPTION:
        if key in desc and key not in payload:
            payload[key] = desc.pop(key)
            hoisted = True
        elif key in desc and key in payload:
            # Prefer non-empty hoisted itinerary over empty/missing root.
            if key == "daily_itinerary":
                root_days = payload.get(key)
                nested_days = desc.get(key)
                if (not root_days) and isinstance(nested_days, list) and nested_days:
                    payload[key] = desc.pop(key)
                    hoisted = True
                else:
                    desc.pop(key, None)
            else:
                desc.pop(key, None)

    # Keep only narrative fields inside trip_description.
    kept = {
        k: desc[k]
        for k in ("overview", "included", "not_included", "summary")
        if k in desc
    }
    if "overview" not in kept and isinstance(desc.get("overview"), str):
        kept["overview"] = desc["overview"]
    payload["trip_description"] = kept or {
        "overview": "",
        "included": [],
        "not_included": [],
    }
    if hoisted:
        logger.info(
            "Hoisted nested package fields out of trip_description: %s",
            sorted(k for k in payload if k != "trip_description"),
        )
    return payload


def normalize_package_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Repair common small-model shape mistakes before schema validation."""
    if "package" in payload and isinstance(payload["package"], dict):
        payload = payload["package"]

    for wrapper in ("data", "result", "output"):
        if wrapper in payload and isinstance(payload[wrapper], dict) and (
            "daily_itinerary" in payload[wrapper]
            or "trip_title" in payload[wrapper]
            or "budget_summary" in payload[wrapper]
        ):
            payload = payload[wrapper]
            break

    payload = _hoist_nested_package_fields(dict(payload))

    normalized: dict[str, Any] = {}
    for key, value in payload.items():
        mapped = _KEY_ALIASES.get(key, key)
        if mapped == key and isinstance(key, str):
            snake = key.strip().lower().replace(" ", "_")
            mapped = _KEY_ALIASES.get(
                snake, snake if snake in TourismPackage.model_fields else key
            )
        if mapped not in normalized:
            normalized[mapped] = value

    if "daily_itinerary" not in normalized and "clusters" in normalized:
        logger.warning(
            "LLM returned RAG-shaped keys instead of package schema: %s",
            sorted(normalized.keys()),
        )

    normalized = _stringify_scalars(normalized)
    return _coerce_nested_shapes(normalized)


def _as_string_list(value: Any) -> list[str]:
    """Coerce list/dict/str into a flat list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, dict):
        return [str(v) for v in value.values() if str(v).strip()]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, dict):
                out.extend(str(v) for v in item.values() if str(v).strip())
            elif item is not None and str(item).strip():
                out.append(str(item))
        return out
    return [str(value)] if str(value).strip() else []


def _coerce_nested_shapes(payload: dict[str, Any]) -> dict[str, Any]:
    """Fix common wrong nested shapes from cloud/reasoning models."""
    love = payload.get("why_you_will_love_this")
    if isinstance(love, str):
        payload["why_you_will_love_this"] = {
            "highlights": [love] if love.strip() else [],
            "special_touches": [],
        }
    elif isinstance(love, list):
        payload["why_you_will_love_this"] = {
            "highlights": _as_string_list(love),
            "special_touches": [],
        }
    elif isinstance(love, dict):
        if "highlights" not in love and "special_touches" not in love:
            values = [str(v) for v in love.values() if str(v).strip()]
            payload["why_you_will_love_this"] = {
                "highlights": values[:6],
                "special_touches": values[6:10],
            }
        else:
            # Keep known keys; drop unexpected sibling keys.
            payload["why_you_will_love_this"] = {
                "highlights": _as_string_list(love.get("highlights")),
                "special_touches": _as_string_list(love.get("special_touches")),
            }

    desc = payload.get("trip_description")
    if isinstance(desc, str):
        payload["trip_description"] = {
            "overview": desc,
            "included": [],
            "not_included": [],
        }
    elif isinstance(desc, dict):
        payload["trip_description"] = {
            "overview": desc.get("overview") or desc.get("summary") or "",
            "included": _as_string_list(desc.get("included")),
            "not_included": _as_string_list(
                desc.get("not_included") or desc.get("excluded")
            ),
        }

    tips = payload.get("essential_travel_tips")
    if isinstance(tips, dict):
        # {"Safety": ["a","b"], "Money": "x"} → list of {category, tips}
        converted = []
        for category, value in tips.items():
            if isinstance(value, list):
                tip_list = [str(v) for v in value]
            elif value is None:
                tip_list = []
            else:
                tip_list = [str(value)]
            converted.append({"category": str(category), "tips": tip_list})
        payload["essential_travel_tips"] = converted
    elif isinstance(tips, str):
        payload["essential_travel_tips"] = [
            {
                "category": "General",
                "tips": [tips] if tips.strip() else [],
            }
        ]
    elif isinstance(tips, list):
        converted = []
        for item in tips:
            if isinstance(item, dict):
                category = item.get("category") or item.get("title") or "General"
                raw_tips = item.get("tips") if "tips" in item else item.get("tip")
                if isinstance(raw_tips, list):
                    tip_list = [str(v) for v in raw_tips]
                elif raw_tips is None:
                    # Whole dict values as tips, excluding category key.
                    tip_list = [
                        str(v)
                        for k, v in item.items()
                        if k not in ("category", "title") and str(v).strip()
                    ]
                else:
                    tip_list = [str(raw_tips)]
                converted.append({"category": str(category), "tips": tip_list})
            elif item is not None and str(item).strip():
                converted.append({"category": "General", "tips": [str(item)]})
        payload["essential_travel_tips"] = converted

    details = payload.get("trip_details")
    if isinstance(details, dict):
        duration = details.get("duration") if isinstance(details.get("duration"), dict) else {}
        budget = details.get("budget") if isinstance(details.get("budget"), dict) else {}
        amount = (
            budget.get("amount")
            or budget.get("total")
            or budget.get("total_cost")
            or details.get("total_budget")
            or ""
        )
        payload["trip_details"] = {
            "duration": {
                "days": "" if duration.get("days") is None else str(duration.get("days")),
                "nights": "" if duration.get("nights") is None else str(duration.get("nights")),
            },
            "trip_type": _as_string_list(details.get("trip_type")),
            "number_of_travelers": str(
                details.get("number_of_travelers") or details.get("travelers") or ""
            ),
            "budget": {
                "amount": "" if amount is None else str(amount),
                "currency": str(budget.get("currency") or "JOD"),
            },
        }

    budget_summary = payload.get("budget_summary")
    if isinstance(budget_summary, dict):
        items = budget_summary.get("items")
        if not isinstance(items, list) or not items:
            breakdown = budget_summary.get("breakdown")
            if isinstance(breakdown, dict):
                items = [
                    {
                        "category": str(key),
                        "estimated_cost": str(value),
                        "notes": "",
                    }
                    for key, value in breakdown.items()
                    if str(key).lower() != "currency"
                ]
            else:
                items = []
        total = (
            budget_summary.get("total_estimated_cost")
            or budget_summary.get("total_cost")
            or budget_summary.get("total")
            or ""
        )
        payload["budget_summary"] = {
            "items": items,
            "total_estimated_cost": "" if total is None else str(total),
        }

    explanations = payload.get("explanations")
    if isinstance(explanations, str):
        payload["explanations"] = {
            "trip_planning_reason": explanations,
            "selection_reason": "",
        }
    elif isinstance(explanations, dict):
        payload["explanations"] = {
            "trip_planning_reason": explanations.get("trip_planning_reason")
            or explanations.get("planning")
            or "",
            "selection_reason": explanations.get("selection_reason")
            or explanations.get("selection")
            or "",
        }

    return payload


_BLANK_MARKERS = {"", "...", "…", "n/a", "na", "todo", "tbd", "placeholder", "fill me"}


def _is_blank(value: str | None) -> bool:
    return (value or "").strip().lower() in _BLANK_MARKERS


def assert_package_matches_request(package: TourismPackage, request: PackageRequest) -> None:
    """Reject packages that ignore the requested trip length."""
    expected = request.duration_days
    got = len(package.days)
    if got != expected:
        raise ReTourValidationError(
            f"days must contain exactly {expected} day objects (got {got})."
        )
    if package.trip.duration_days and package.trip.duration_days != expected:
        raise ReTourValidationError(
            f"trip.duration_days must be {expected} (got {package.trip.duration_days})."
        )
    expected_nights = max(expected - 1, 0)
    if package.trip.nights and package.trip.nights != expected_nights:
        raise ReTourValidationError(
            f"trip.nights must be {expected_nights} (got {package.trip.nights})."
        )
    assert_package_complete(package)


def assert_package_complete(package: TourismPackage) -> None:
    """Reject truncated packages that pass the loose Pydantic schema."""
    if _is_blank(package.trip_title) and _is_blank(package.trip.title):
        raise ReTourValidationError("trip title is empty — package looks truncated.")
    if not package.days:
        raise ReTourValidationError("package has no days.")
    if not any(day.schedule for day in package.days):
        raise ReTourValidationError("package has no grounded schedule items.")


def validate_tourism_package(raw_text: str) -> TourismPackage:
    """Parse and validate LLM output into a TourismPackage."""
    from app.validation.package import parse_package_json, validate_schema

    try:
        payload = parse_package_json(raw_text)
        return validate_schema(payload)
    except LLMResponseParseError:
        raise
    except ValidationError as exc:
        errors = [
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in exc.errors()
        ]
        raise ReTourValidationError(f"Package validation failed: {'; '.join(errors)}") from exc


def parse_task_payload(raw_text: str) -> dict[str, Any]:
    """Parse a single-task JSON object and normalize key aliases."""
    payload = extract_json_object(raw_text)
    if not isinstance(payload, dict):
        raise LLMResponseParseError("Task JSON root must be an object")
    return normalize_package_payload(payload)


def require_task_keys(payload: dict[str, Any], keys: tuple[str, ...], task_name: str) -> None:
    missing = [k for k in keys if k not in payload]
    if missing:
        raise ReTourValidationError(
            f"{task_name} response missing keys: {', '.join(missing)}"
        )
