"""End-to-end Brain pipeline with a mocked LLM and retriever."""

from __future__ import annotations

import json

import pytest

from app.agents.tourism_planner import TourismPlannerAgent
from app.core.interfaces.llm import LLMResponse
from app.schemas.request.package_request import PackageRequest
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST, VALID_PACKAGE_RESPONSE


class _FakeLLM:
    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.provider_name = "test"
        self.model_name = "gpt-oss-test"
        self.max_tokens = 2048

    async def generate(self, messages, *, system_prompt=None, max_tokens=None):  # noqa: ANN001
        _ = messages, system_prompt, max_tokens
        return LLMResponse(
            content=json.dumps(self._payload),
            model="gpt-oss-test",
            provider="test",
        )

    async def close(self) -> None:
        return None


class _FakeKnowledge:
    async def search_for_itinerary(self, request):  # noqa: ANN001
        return {
            "duration_days": request.duration_days,
            "clusters": [
                {
                    "cluster_id": 0,
                    "theme": "Petra heritage",
                    "summary": "Petra day",
                    "pois": [
                        {
                            "id": "poi_test_petra",
                            "name": "Petra Visitor Center",
                            "entity_type": "poi",
                            "region": "Ma'an Governorate",
                            "city": "Wadi Musa",
                            "why_retrieved": ["mustVisit:Petra"],
                            "facts": {
                                "identity": {"category": "Heritage"},
                                "semantic": {"summary": "Gateway to Petra"},
                            },
                            "latitude": 30.322,
                            "longitude": 35.479,
                        }
                    ],
                    "hotels": [],
                    "events": [],
                }
            ],
            "meta": {"rag_status": "ok", "source": "test", "planning_lock": "plan Petra first"},
        }

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_full_pipeline_wizard_to_package(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.agents.tourism_planner.save_generation_case",
        lambda **kwargs: "case-test",
    )
    async def fake_weather(**kwargs):
        return [], "unavailable"

    monkeypatch.setattr("app.context.builder.fetch_weather", fake_weather)
    request = PackageRequest.model_validate(VALID_PACKAGE_REQUEST)
    agent = TourismPlannerAgent(
        llm_manager=_FakeLLM(VALID_PACKAGE_RESPONSE),
        knowledge=_FakeKnowledge(),
    )
    package, metadata, knowledge = await agent.generate_package(request)
    assert package.trip.duration_days == 6
    assert len(package.days) == 6
    assert metadata.model == "gpt-oss-test"
    assert knowledge["meta"]["rag_status"] == "ok"
    names = [item.name for day in package.days for item in day.schedule]
    assert "Invented Castle" not in names
