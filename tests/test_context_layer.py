"""Context layer tests."""

from __future__ import annotations

import pytest

from app.context.builder import build_planning_context, climate_for_month
from app.planning.profile import normalize_tourist_profile
from app.schemas.request.package_request import PackageRequest
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST


def test_summer_climate_is_deterministic() -> None:
    climate = climate_for_month(8)
    assert climate.heat_risk == "high"
    assert "morning" in climate.outdoor_guidance.lower()


@pytest.mark.asyncio
async def test_context_is_structured(monkeypatch) -> None:
    async def fake_weather(**kwargs):
        return [], "unavailable"

    monkeypatch.setattr("app.context.builder.fetch_weather", fake_weather)
    request = PackageRequest.model_validate(VALID_PACKAGE_REQUEST)
    profile = normalize_tourist_profile(request)
    context = await build_planning_context(profile)
    payload = context.prompt_dict()
    assert payload["trip_window"]["duration_days"] == 6
    assert payload["trip_window"]["exploration_days"] == 5
    assert payload["geographic"]["must_visit"] == ["Petra", "Dead Sea"]
    assert payload["pace"]["sights_per_day"] >= 2
    assert payload["budget"]["band"]
    assert payload["weather_status"] == "unavailable"
    assert "Never invent" in payload["decision_rules"][0]
    assert payload["decisions"]
    assert payload["day_intents"]
    assert len(payload["day_intents"]) == 6
    assert {day["region"] for day in payload["day_intents"]} <= {
        "Petra",
        "Wadi Rum",
        "Dead Sea",
        "Amman",
        "Aqaba",
    }
    jargon = ("poi", "sme", "catalog", "leftover", "retrieval", "grounded", "rag")
    for decision in payload["decisions"]:
        blob = f"{decision['title']} {decision['effect']}".lower()
        assert not any(word in blob for word in jargon)
    route = next(item for item in payload["decisions"] if item["code"] == "day_route")
    assert "Petra" in route["effect"]
    assert "Locked route" not in route["effect"]
    from app.context.builder import tourist_planning_reason

    brief = tourist_planning_reason(context)
    assert "Each day stays in one area" not in brief
    assert "About 3 places" not in brief
    assert "Amman" in brief or "land" in brief.lower()
