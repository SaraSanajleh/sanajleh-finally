"""Tests for FastAPI endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.response.package_response import (
    PackageGenerationMetadata,
    PackageGenerationResponse,
    TourismPackage,
)
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST, VALID_PACKAGE_RESPONSE


@pytest.fixture
def mock_package_response() -> PackageGenerationResponse:
    return PackageGenerationResponse(
        package=TourismPackage.model_validate(VALID_PACKAGE_RESPONSE),
        metadata=PackageGenerationMetadata(
            model="test-model",
            provider="test",
            mode="build",
            latencyMs=100.0,
            retries=0,
        ),
    )


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_generate_package_endpoint(mock_package_response: PackageGenerationResponse) -> None:
    with patch(
        "app.services.package_service.PackageService.generate",
        new=AsyncMock(return_value=mock_package_response),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/packages/generate",
                json=VALID_PACKAGE_REQUEST,
            )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "package" in body
    assert body["package"]["trip_title"] == VALID_PACKAGE_RESPONSE["trip_title"]


@pytest.mark.asyncio
async def test_generate_package_invalid_request() -> None:
    invalid = {**VALID_PACKAGE_REQUEST}
    invalid["travelers"] = {
        **VALID_PACKAGE_REQUEST["travelers"],
        "children": 1,
        "childrenAges": [],
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/packages/generate", json=invalid)

    assert response.status_code == 422
    assert response.json()["success"] is False
