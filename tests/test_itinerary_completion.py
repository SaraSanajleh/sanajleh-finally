"""Day-count helpers now live in validation.package."""

from __future__ import annotations

from app.planning.profile import normalize_tourist_profile
from app.retrieval.knowledge import RetrievedKnowledge
from app.schemas.request.package_request import PackageRequest
from app.schemas.response.package_response import TourismPackage
from app.validation.package import apply_profile_facts, ground_and_repair
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST, VALID_PACKAGE_RESPONSE


def test_missing_days_are_resized_to_request_length() -> None:
    request = PackageRequest.model_validate(VALID_PACKAGE_REQUEST)
    profile = normalize_tourist_profile(request)
    package = apply_profile_facts(TourismPackage.model_validate(VALID_PACKAGE_RESPONSE), profile)
    repaired, errors = ground_and_repair(package, profile, RetrievedKnowledge(status="ok"), {}, [])
    assert len(repaired.days) == 6
    assert errors
