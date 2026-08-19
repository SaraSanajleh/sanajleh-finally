"""Prompt builder keeps knowledge, SME, and wizard objects separated."""

from __future__ import annotations

from app.context.models import (
    BudgetFrame,
    ClimateWindow,
    GeographicFrame,
    PaceFrame,
    PlanningContext,
    TravelerFrame,
)
from app.planning.profile import normalize_tourist_profile
from app.prompts.builder import PromptBuilder
from app.retrieval.knowledge import DayShortlist, KnowledgeCard, RetrievedKnowledge
from app.schemas.request.package_request import PackageRequest
from app.sme.models import SMEMatch, SMERecord
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST


def test_prompt_contains_isolated_sections() -> None:
    request = PackageRequest.model_validate(VALID_PACKAGE_REQUEST)
    profile = normalize_tourist_profile(request)
    context = PlanningContext(
        trip_window={"duration_days": 5},
        geographic=GeographicFrame(arrival_airport="AMM"),
        traveler=TravelerFrame(group_type="couple", adults=2, total_travelers=2),
        pace=PaceFrame(
            trip_pace="Balanced",
            activity_level="Moderate",
            sights_per_day=3,
            meals_per_day=2,
            max_schedule_items=6,
        ),
        budget=BudgetFrame(total=1500, band="moderate", per_day=300, guidance=""),
        climate=ClimateWindow(
            month=8,
            season="hot_dry_summer",
            typical_pattern="hot",
            outdoor_guidance="mornings",
            heat_risk="high",
        ),
    )
    castle = KnowledgeCard(item_id="poi_1", entity_type="poi", name="Ajloun Castle")
    knowledge = RetrievedKnowledge(
        status="ok",
        pois=[castle],
        day_shortlists=[
            DayShortlist(day=1, region="Ajloun", region_key="ajloun", theme="Ajloun", pois=[castle])
        ],
    )
    sme = SMEMatch(
        record=SMERecord(sme_id="SME-000001", sme_type="tour_guide", name="Ahmad Momani"),
        score=0.8,
        reasons=["Matches interests: history"],
        role="Local guide",
    )
    prompt = PromptBuilder().user_prompt(
        profile=profile,
        context=context,
        knowledge=knowledge,
        smes=[sme],
        wizard_json=request.model_dump(mode="json"),
    )
    assert "## Wizard request" in prompt
    assert "## Why context changed this plan" in prompt
    assert "## Ranked knowledge for each locked day" in prompt
    assert "## Trip SME team" in prompt
    assert "Ajloun Castle" in prompt
    assert "SME-000001" in prompt
    assert "Never invent" in PromptBuilder().system_prompt()
