"""Tests for request schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.request.package_request import PackageRequest
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST


def test_valid_package_request_parses() -> None:
    request = PackageRequest.model_validate(VALID_PACKAGE_REQUEST)
    assert request.mode.value == "build"
    assert request.duration_days == 5
    assert request.total_travelers == 2


def test_children_ages_must_match_count() -> None:
    payload = {**VALID_PACKAGE_REQUEST}
    payload["travelers"] = {
        **VALID_PACKAGE_REQUEST["travelers"],
        "children": 2,
        "childrenAges": ["8"],
    }
    with pytest.raises(ValidationError):
        PackageRequest.model_validate(payload)


def test_interests_minimum_one() -> None:
    payload = {**VALID_PACKAGE_REQUEST}
    payload["preferences"] = {**VALID_PACKAGE_REQUEST["preferences"], "interests": []}
    with pytest.raises(ValidationError):
        PackageRequest.model_validate(payload)


def test_custom_duration_allowed() -> None:
    payload = {**VALID_PACKAGE_REQUEST}
    payload["trip"] = {**VALID_PACKAGE_REQUEST["trip"], "duration": "10"}
    request = PackageRequest.model_validate(payload)
    assert request.duration_days == 10


def test_adults_minimum_one() -> None:
    payload = {**VALID_PACKAGE_REQUEST}
    payload["travelers"] = {**VALID_PACKAGE_REQUEST["travelers"], "adults": 0}
    with pytest.raises(ValidationError):
        PackageRequest.model_validate(payload)
