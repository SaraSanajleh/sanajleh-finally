"""FastAPI dependency injection container."""

from __future__ import annotations

from functools import lru_cache

from app.agents.package_builder_agent import PackageBuilderAgent
from app.llm.manager import LLMManager
from app.services.package_service import PackageService
from app.services.prompt_service import PromptService
from app.services.retriever_client import HttpRetrieverClient, NullTourismKnowledgeProvider


@lru_cache
def get_prompt_service() -> PromptService:
    return PromptService()


@lru_cache
def get_llm_manager() -> LLMManager:
    return LLMManager()


@lru_cache
def get_knowledge_provider():
    from app.config.settings import get_app_settings

    settings = get_app_settings()
    if settings.retriever_enabled:
        return HttpRetrieverClient(settings=settings)
    return NullTourismKnowledgeProvider()


@lru_cache
def get_package_builder_agent() -> PackageBuilderAgent:
    return PackageBuilderAgent(
        llm_manager=get_llm_manager(),
        prompt_service=get_prompt_service(),
        knowledge=get_knowledge_provider(),
    )


def get_package_service() -> PackageService:
    return PackageService(agent=get_package_builder_agent())


async def shutdown_resources() -> None:
    """Release cached singleton resources on application shutdown."""
    manager = get_llm_manager()
    await manager.close()
    knowledge = get_knowledge_provider()
    close = getattr(knowledge, "close", None)
    if callable(close):
        await close()
    get_llm_manager.cache_clear()
    get_package_builder_agent.cache_clear()
    get_prompt_service.cache_clear()
    get_knowledge_provider.cache_clear()
