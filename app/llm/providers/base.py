"""Abstract base for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.interfaces.llm import LLMGenerationConfig, LLMMessage, LLMResponse


class BaseLLMProvider(ABC):
    """Shared provider contract with typed method signatures."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider identifier."""

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        config: LLMGenerationConfig,
    ) -> LLMResponse:
        """Generate a completion."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Check provider availability."""
