"""Package generation service — API-facing business layer."""

from __future__ import annotations

import asyncio

from app.agents.package_builder_agent import PackageBuilderAgent
from app.core.exceptions import ValidationError as ReTourValidationError
from app.schemas.request.package_request import PackageRequest
from app.schemas.response.package_response import PackageGenerationResponse
from app.utils.logging import get_logger
from app.validators.package_request_validator import validate_package_request

logger = get_logger(__name__)

# Ollama handles one inference at a time — serialize requests (queue) instead of rejecting.
_generation_lock = asyncio.Lock()


class PackageService:
    """
    Service layer between API routes and the Package Builder Agent.

    Handles validation, logging, and response assembly.
    Routes must never call the agent directly.
    """

    def __init__(self, agent: PackageBuilderAgent) -> None:
        self._agent = agent

    async def generate(self, request: PackageRequest) -> PackageGenerationResponse:
        """Validate request and delegate to the Package Builder Agent."""
        # Validate before waiting on the lock so bad requests fail immediately.
        try:
            validate_package_request(request)
        except ReTourValidationError:
            raise

        if _generation_lock.locked():
            logger.info(
                "Another package generation is running — queueing this request "
                "(mode=%s, duration=%sd)",
                request.mode.value,
                request.duration_days,
            )

        async with _generation_lock:
            logger.info(
                "Generating package: mode=%s, duration=%sd, budget=%s JOD",
                request.mode.value,
                request.duration_days,
                request.trip.totalBudget,
            )

            package, metadata, knowledge = await self._agent.generate_package(request)
            return PackageGenerationResponse(
                package=package,
                metadata=metadata,
                knowledge=knowledge,
            )

    async def generate_with_progress(
        self,
        request: PackageRequest,
        on_stage,
    ) -> PackageGenerationResponse:
        try:
            validate_package_request(request)
        except ReTourValidationError:
            raise
        async with _generation_lock:
            package, metadata, knowledge = await self._agent.generate_package(
                request, on_stage=on_stage
            )
            return PackageGenerationResponse(
                package=package,
                metadata=metadata,
                knowledge=knowledge,
            )
