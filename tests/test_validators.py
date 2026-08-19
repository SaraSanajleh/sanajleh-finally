"""Tests for response schema and JSON parsing."""

from __future__ import annotations

import json

import pytest

from app.core.exceptions import LLMResponseParseError, ValidationError
from app.schemas.response.package_response import TourismPackage
from app.validators.json_parser import extract_json_object
from app.validators.package_response_validator import validate_tourism_package
from tests.fixtures.sample_payloads import VALID_PACKAGE_RESPONSE


def test_valid_package_response_parses() -> None:
    package = TourismPackage.model_validate(VALID_PACKAGE_RESPONSE)
    assert package.trip_title == "Anniversary Jordan Discovery"
    assert len(package.days) == 1


def test_extract_json_ignores_thinking_prose_then_finds_object() -> None:
    prose = (
        "We need to produce a single JSON object with fields: welcome_message, "
        "trip_title, daily_itinerary.\n"
        '{"welcome_message":"Hi","trip_title":"Jordan","daily_itinerary":'
        '[{"day_number":"1","day_title":"Amman","day_summary":"Walk",'
        '"activities":[{"activity_title":"Citadel","location":"Amman"}]}]}'
    )
    parsed = extract_json_object(prose)
    assert parsed["trip_title"] == "Jordan"
    assert parsed["welcome_message"] == "Hi"


def test_extract_json_from_markdown_fence() -> None:
    raw = f"Here is the package:\n```json\n{json.dumps(VALID_PACKAGE_RESPONSE)}\n```"
    parsed = extract_json_object(raw)
    assert parsed["welcome_message"] == VALID_PACKAGE_RESPONSE["welcome_message"]


def test_extract_json_plain_object() -> None:
    raw = json.dumps(VALID_PACKAGE_RESPONSE)
    parsed = extract_json_object(raw)
    assert "trip" in parsed or "trip_title" in parsed


def test_extract_json_raises_on_empty() -> None:
    with pytest.raises(LLMResponseParseError):
        extract_json_object("")


def test_validate_tourism_package_success() -> None:
    raw = json.dumps(VALID_PACKAGE_RESPONSE)
    package = validate_tourism_package(raw)
    assert isinstance(package, TourismPackage)


def test_validate_tourism_package_invalid() -> None:
    with pytest.raises((ValidationError, LLMResponseParseError)):
        validate_tourism_package("this is not json {")


def test_extract_json_repairs_missing_day_brace_and_tips_array() -> None:
    """gpt-oss often forgets `{` between days and `]` on tips arrays."""
    raw = (
        '{"welcome_message":"Hi","trip_title":"North Loop","daily_itinerary":['
        '{"day_number":"1","day_title":"Jerash","day_summary":"Ruins",'
        '"activities":[{"activity_title":"Souk","location":"Jerash"}],'
        '"activity_alternatives":[]},'
        '"day_number":"2","day_title":"Ajloun","day_summary":"Forest",'
        '"activities":[{"activity_title":"Castle","location":"Ajloun"}],'
        '"activity_alternatives":[]}],'
        '"Essential Travel Tips":['
        '{"category":"Safety","tips":["Carry water"},'
        '{"category":"Money","tips":["Bring cash"]}'
        ']}'
    )
    parsed = extract_json_object(raw)
    assert len(parsed["daily_itinerary"]) == 2
    assert parsed["daily_itinerary"][1]["day_title"] == "Ajloun"
    tips = parsed.get("Essential Travel Tips") or parsed.get("essential_travel_tips")
    assert tips[0]["tips"] == ["Carry water"]
    assert tips[1]["tips"] == ["Bring cash"]


def test_validate_accepts_new_package_shape() -> None:
    package = validate_tourism_package(json.dumps(VALID_PACKAGE_RESPONSE))
    assert package.trip.duration_days == 5
    assert package.days[0].schedule[0].name == "Petra Visitor Center"


def test_extract_json_closes_missing_final_brace_and_keeps_itinerary() -> None:
    raw = (
        '{"welcome_message":"Hi","trip_title":"Trip","trip_description":{'
        '"overview":"O","included":[],"not_included":[],'
        '"daily_itinerary":[{"day_number":"1","day_title":"D","day_summary":"S",'
        '"activities":[{"activity_title":"A","location":"L"}]}]}'
        # missing final closing brace for root
    )
    parsed = extract_json_object(raw)
    # After parse, nested itinerary may still be under trip_description until normalize.
    assert "daily_itinerary" in parsed or (
        isinstance(parsed.get("trip_description"), dict)
        and "daily_itinerary" in parsed["trip_description"]
    )


def test_extract_json_repairs_truncated_object() -> None:
    """LLM sometimes hits max_tokens mid-object — repair should close braces."""
    truncated = (
        '{"welcome_message":"Hi","trip_title":"Jordan Trip","daily_itinerary":['
        '{"day_number":"1","day_title":"Amman","activities":[{"activity_title":"Citadel"'
    )
    parsed = extract_json_object(truncated)
    assert parsed["trip_title"] == "Jordan Trip"
    assert isinstance(parsed["daily_itinerary"], list)


def test_legacy_daily_itinerary_is_mapped_to_days() -> None:
    raw = {
        "trip_title": "North Loop",
        "welcome_message": "Welcome",
        "daily_itinerary": [
            {
                "day_number": "1",
                "day_title": "Jerash",
                "day_summary": "Ruins",
                "activities": [
                    {
                        "activity_title": "Jerash Heritage Souk",
                        "location": "Jerash",
                        "start_time": "09:00",
                    }
                ],
            }
        ],
    }
    package = validate_tourism_package(json.dumps(raw))
    assert len(package.days) == 1
    assert package.days[0].schedule[0].name == "Jerash Heritage Souk"
