import pytest

from app.context.builder import build_planning_context
from app.planning.itinerary import build_locked_package
from app.planning.profile import normalize_tourist_profile
from app.retrieval.composer import compose_trip_knowledge
from app.schemas.request.package_request import PackageRequest
from app.sme.matcher import select_package_smes
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST


@pytest.mark.asyncio
async def test_skeleton_keeps_jerash_in_jerash(monkeypatch) -> None:
    async def fake_weather(**kwargs):
        return [], "unavailable"

    monkeypatch.setattr("app.context.builder.fetch_weather", fake_weather)
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "preferredRegions": ["Ajloun", "Jerash"],
            "totalBudget": 900,
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "interests": ["history", "culture"],
            "mustVisit": ["Jerash"],
            "placesToAvoid": "",
        },
    }
    request = PackageRequest.model_validate(payload)
    profile = normalize_tourist_profile(request)
    context = await build_planning_context(profile)
    knowledge = compose_trip_knowledge(
        {"duration_days": 3, "clusters": [], "meta": {"rag_status": "unavailable"}},
        profile,
        context,
    )
    package = build_locked_package(profile, context, knowledge, select_package_smes(profile))
    regions = {intent.region_key for intent in context.day_intents}
    assert regions <= {"ajloun", "jerash", "amman"}
    assert context.day_intents[0].is_arrival_day
    assert context.day_intents[0].overnight_key == "amman"
    assert len(package.days) == 4
    assert len(context.day_intents) == 4
    arrival_day = package.days[0]
    assert arrival_day.is_arrival_day
    assert "arrival" in arrival_day.theme.lower()
    assert package.days[1].is_arrival_day is False
    arrival_pois = [item for item in arrival_day.schedule if item.type == "poi"]
    assert len(arrival_pois) >= 2
    assert any(item.type == "hotel" for item in arrival_day.schedule)
    assert sum(1 for item in arrival_day.schedule if item.type == "hotel") == 1
    jerash_days = [day for day in package.days if "jerash" in day.region.lower()]
    assert jerash_days
    for day in jerash_days:
        assert day.smes == []
        for item in day.schedule:
            blob = f"{item.name} {item.location}".lower()
            assert "irbid" not in blob
    names = [item.name for day in package.days for item in day.schedule]
    assert any("jerash" in name.lower() for name in names)
    assert package.planning.decisions
    types = [sme.sme_type for sme in package.sme_value.recommended]
    assert types.count("tour_guide") <= 1
    assert types.count("tour_operator") <= 1
    assert any(sme.known_for or sme.specs for sme in package.sme_value.recommended)
    assert package.budget.items
    assert any(item.category == "Stays" for item in package.budget.items)
