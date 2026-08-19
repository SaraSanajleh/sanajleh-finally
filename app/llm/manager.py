"""LLM Manager — single entry point for all model interactions."""

from __future__ import annotations

from app.config.settings import LLMSettings, get_llm_settings
from app.core.exceptions import LLMError
from app.core.interfaces.llm import LLMGenerationConfig, LLMMessage, LLMResponse, LLMProvider
from app.llm.factory import create_llm_provider
from app.utils.logging import get_logger

logger = get_logger(__name__)


class LLMManager:
    """
    Abstraction layer between agents and LLM backends.

    Agents never call Ollama, OpenAI, or Claude directly — only this manager.
    """

    def __init__(
        self,
        settings: LLMSettings | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        self._settings = settings or get_llm_settings()
        self._provider = provider or create_llm_provider(self._settings)

    @property
    def provider_name(self) -> str:
        return self._provider.provider_name

    @property
    def model_name(self) -> str:
        return self._settings.model_name

    @property
    def max_tokens(self) -> int:
        return int(self._settings.max_tokens)

    def _build_generation_config(self, *, max_tokens: int | None = None) -> LLMGenerationConfig:
        tokens = self._settings.max_tokens if max_tokens is None else max_tokens
        return LLMGenerationConfig(
            temperature=self._settings.temperature,
            top_p=self._settings.top_p,
            max_tokens=max(256, int(tokens)),
            timeout_seconds=self._settings.timeout_seconds,
        )

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        Generate a completion with retry logic.

        Prepends an optional system message before provider invocation.
        ``max_tokens`` overrides the yaml default for this call only (two-phase gen).
        """
        full_messages: list[LLMMessage] = []
        if system_prompt:
            full_messages.append(LLMMessage(role="system", content=system_prompt))
        full_messages.extend(messages)

        max_attempts = self._settings.max_retries + 1
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                self._settings.reload()
                config = self._build_generation_config(max_tokens=max_tokens)
                logger.info(
                    "LLM generate attempt %s/%s via %s (%s) timeout=%ss max_tokens=%s think=%s",
                    attempt,
                    max_attempts,
                    self._provider.provider_name,
                    self._settings.model_name,
                    int(config.timeout_seconds),
                    config.max_tokens,
                    self._settings.ollama_think,
                )
                return await self._provider.generate(full_messages, config)
            except LLMError as exc:
                last_error = exc
                logger.warning("LLM attempt %s failed: %s", attempt, exc.message)
                if not exc.retryable or attempt >= max_attempts:
                    raise

        raise LLMError(
            f"LLM generation failed after {max_attempts} attempts: {last_error}",
            retryable=False,
        )

    async def health_check(self) -> bool:
        """Delegate health check to the active provider."""
        return await self._provider.health_check()

    async def close(self) -> None:
        """Release provider resources."""
        close_method = getattr(self._provider, "close", None)
        if callable(close_method):
            await close_method()
