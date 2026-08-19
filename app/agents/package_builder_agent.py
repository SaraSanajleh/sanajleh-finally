"""Compatibility wrapper — the Brain uses TourismPlannerAgent."""

from __future__ import annotations

from typing import Any

from app.agents.tourism_planner import TourismPlannerAgent
from app.config.settings import AppSettings, get_app_settings
from app.llm.manager import LLMManager
from app.prompts.builder import PromptBuilder
from app.schemas.request.package_request import PackageRequest
from app.schemas.response.package_response import PackageGenerationMetadata, TourismPackage
from app.services.prompt_service import PromptService
from app.services.retriever_client import TourismKnowledgeProvider


class PackageBuilderAgent:
    """Public agent facade used by PackageService and DI."""

    def __init__(
        self,
        llm_manager: LLMManager,
        prompt_service: PromptService | None = None,
        knowledge: TourismKnowledgeProvider | None = None,
        settings: AppSettings | None = None,
    ) -> None:
        _ = prompt_service
        self._planner = TourismPlannerAgent(
            llm_manager=llm_manager,
            knowledge=knowledge,
            settings=settings or get_app_settings(),
            prompt_builder=PromptBuilder(settings or get_app_settings()),
        )

    async def generate_package(
        self,
        request: PackageRequest,
        on_stage: Any = None,
    ) -> tuple[TourismPackage, PackageGenerationMetadata, dict[str, Any]]:
        return await self._planner.generate_package(request, on_stage=on_stage)
