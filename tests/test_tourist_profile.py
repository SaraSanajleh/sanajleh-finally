"""Tests for wizard → TouristProfile normalization and constraints."""

from __future__ import annotations

from app.planning.constraints import evaluate_constraints, item_is_avoided
from app.planning.profile import normalize_tourist_profile
from app.schemas.request.package_request import PackageRequest
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST


def test_normalize_profile_keeps_wizard_facts() -> None:
    request = PackageRequest.model_validate(VALID_PACKAGE_REQUEST)
    profile = normalize_tourist_profile(request)
    assert profile.duration_days == 6
    assert profile.exploration_days == 5
    assert profile.nights == 5
    assert profile.group_type == "couple"
    assert "history" in profile.interests
    assert profile.must_visit == ["Petra", "Dead Sea"]
    assert profile.total_budget == 1500


def test_places_to_avoid_are_real_exclusions() -> None:
    payload = {**VALID_PACKAGE_REQUEST}
    payload["preferences"] = {
        **VALID_PACKAGE_REQUEST["preferences"],
        "placesToAvoid": "Petra, Wadi Rum",
    }
    request = PackageRequest.model_validate(payload)
    profile = normalize_tourist_profile(request)
    assert item_is_avoided("Petra Visitor Center", "Ma'an", "", profile)
    assert not item_is_avoided("Ajloun Castle", "Ajloun", "", profile)


def test_must_visit_constraint_status() -> None:
    request = PackageRequest.model_validate(VALID_PACKAGE_REQUEST)
    profile = normalize_tourist_profile(request)
    partial = evaluate_constraints(profile, ["Petra Treasury"], ["Ma'an Governorate"])
    assert partial["status"] == "partially_satisfied"
    assert partial["unmet"][0]["item"] == "Dead Sea"
    ok = evaluate_constraints(
        profile,
        ["Petra Treasury", "Dead Sea Panorama"],
        ["Ma'an", "Dead Sea"],
    )
    assert ok["status"] == "satisfied"
