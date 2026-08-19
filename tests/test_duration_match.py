"""Ensure package day count must match the traveler request."""

from __future__ import annotations

import pytest

from app.core.exceptions import ValidationError as ReTourValidationError
from app.schemas.request.package_request import PackageRequest
from app.schemas.response.package_response import TourismPackage
from app.validators.package_response_validator import (
    assert_package_complete,
    assert_package_matches_request,
)
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST, VALID_PACKAGE_RESPONSE


def test_assert_rejects_wrong_day_count() -> None:
    request = PackageRequest.model_validate(VALID_PACKAGE_REQUEST)
    package = TourismPackage.model_validate(VALID_PACKAGE_RESPONSE)
    with pytest.raises(ReTourValidationError, match="exactly 5 day"):
        assert_package_matches_request(package, request)


def test_assert_accepts_matching_day_count() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {**VALID_PACKAGE_REQUEST["trip"], "duration": "1"},
    }
    request = PackageRequest.model_validate(payload)
    package = TourismPackage.model_validate(VALID_PACKAGE_RESPONSE)
    data = package.model_dump()
    data["trip"]["duration_days"] = 1
    data["trip"]["nights"] = 0
    package = TourismPackage.model_validate(data)
    assert_package_matches_request(package, request)


def test_assert_rejects_empty_schedule() -> None:
    data = TourismPackage.model_validate(VALID_PACKAGE_RESPONSE).model_dump()
    data["days"][0]["schedule"] = []
    package = TourismPackage.model_validate(data)
    with pytest.raises(ReTourValidationError, match="no grounded schedule"):
        assert_package_complete(package)
