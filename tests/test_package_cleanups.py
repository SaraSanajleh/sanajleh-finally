"""Grounding repairs replace the old meal/alternative cleanup suite."""

from __future__ import annotations

from app.planning.profile import normalize_tourist_profile
from app.retrieval.knowledge import KnowledgeCard, RetrievedKnowledge
from app.schemas.request.package_request import PackageRequest
from app.schemas.response.package_response import TourismPackage
from app.validation.package import apply_profile_facts, ground_and_repair
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST, VALID_PACKAGE_RESPONSE


def test_duplicate_non_hotel_ids_are_dropped() -> None:
    request = PackageRequest.model_validate(VALID_PACKAGE_REQUEST)
    profile = normalize_tourist_profile(request)
    package = apply_profile_facts(TourismPackage.model_validate(VALID_PACKAGE_RESPONSE), profile)
    data = package.model_dump(mode="python")
    data["days"][0]["schedule"].append(dict(data["days"][0]["schedule"][0]))
    package = TourismPackage.model_validate(data)
    knowledge = RetrievedKnowledge(
        status="ok",
        pois=[
            KnowledgeCard(
                item_id="poi_test_petra",
                entity_type="poi",
                name="Petra Visitor Center",
                region="Ma'an Governorate",
            )
        ],
    )
    repaired, _ = ground_and_repair(package, profile, knowledge, {}, [])
    ids = [item.item_id for item in repaired.days[0].schedule]
    assert ids.count("poi_test_petra") == 1
