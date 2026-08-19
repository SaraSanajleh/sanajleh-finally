"""Tests for request business-rule validation."""

from __future__ import annotations

import pytest

from app.core.exceptions import ValidationError
from app.schemas.request.package_request import PackageRequest
from app.validators.package_request_validator import validate_package_request
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST


def test_validate_package_request_success() -> None:
    request = PackageRequest.model_validate(VALID_PACKAGE_REQUEST)
    result = validate_package_request(request)
    assert result is request


def test_validate_rejects_unrealistic_budget() -> None:
    payload = {**VALID_PACKAGE_REQUEST}
    payload["trip"] = {**VALID_PACKAGE_REQUEST["trip"], "totalBudget": 50, "duration": "5"}
    request = PackageRequest.model_validate(payload)
    with pytest.raises(ValidationError):
        validate_package_request(request)
