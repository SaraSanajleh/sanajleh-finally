"""Derived wizard facts are applied after generation."""

from __future__ import annotations

from app.planning.profile import normalize_tourist_profile
from app.schemas.request.package_request import PackageRequest
from app.schemas.response.package_response import TourismPackage
from app.validation.package import apply_profile_facts
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST, VALID_PACKAGE_RESPONSE


def test_apply_derived_facts_from_wizard() -> None:
    request = PackageRequest.model_validate(VALID_PACKAGE_REQUEST)
    profile = normalize_tourist_profile(request)
    package = TourismPackage.model_validate(VALID_PACKAGE_RESPONSE)
    filled = apply_profile_facts(package, profile)
    assert filled.trip.duration_days == 6
    assert filled.trip.nights == 5
    assert filled.traveler_profile.total_travelers == 2
    assert filled.budget.traveler_budget == 1500
    assert filled.package_id
