"""Factory for creating LLM providers from configuration."""

from __future__ import annotations

from app.config.settings import LLMSettings
from app.core.exceptions import LLMError
from app.core.interfaces.llm import LLMProvider
from app.llm.providers.ollama_provider import OllamaProvider


def create_llm_provider(settings: LLMSettings) -> LLMProvider:
    """
    Instantiate the configured LLM provider.

    Adding a new provider requires only a new class and one branch here.
    """
    provider_name = settings.provider.lower()

    if provider_name == "ollama":
        return OllamaProvider(settings)

    raise LLMError(f"Unsupported LLM provider: {provider_name}", retryable=False)
