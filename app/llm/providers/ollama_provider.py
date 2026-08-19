"""Ollama LLM provider — local model inference."""

from __future__ import annotations

import json
import re

import httpx

from app.config.settings import LLMSettings
from app.core.exceptions import LLMError, LLMTimeoutError
from app.core.interfaces.llm import LLMGenerationConfig, LLMMessage, LLMResponse
from app.llm.providers.base import BaseLLMProvider
from app.utils.logging import get_logger

logger = get_logger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Provider for Ollama-served models (Qwen, Llama, Gemma, Mistral, etc.)."""

    def __init__(self, settings: LLMSettings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client
        self._owns_client = client is None

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def _chat_url(self) -> str:
        base = self._settings.ollama_base_url.rstrip("/")
        path = self._settings.ollama_api_path
        return f"{base}{path}"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client

    async def generate(
        self,
        messages: list[LLMMessage],
        config: LLMGenerationConfig,
    ) -> LLMResponse:
        self._settings.reload()
        client = await self._get_client()
        payload: dict = {
            "model": self._settings.model_name,
            "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
            "stream": False,
            "options": {
                "temperature": config.temperature,
                "top_p": config.top_p,
                "num_predict": config.max_tokens,
            },
        }
        if self._settings.ollama_num_ctx:
            payload["options"]["num_ctx"] = self._settings.ollama_num_ctx
        if self._settings.ollama_num_gpu is not None:
            payload["options"]["num_gpu"] = self._settings.ollama_num_gpu
        if self._settings.ollama_think is not None:
            # Top level only: `think` is a request field, not a sampling option.
            payload["think"] = self._settings.ollama_think
        ollama_format = self._settings.ollama_format
        if ollama_format:
            payload["format"] = ollama_format
        if self._settings.ollama_keep_alive:
            payload["keep_alive"] = self._settings.ollama_keep_alive

        try:
            response = await client.post(
                self._chat_url,
                json=payload,
                timeout=httpx.Timeout(config.timeout_seconds),
            )
            if response.status_code == 404:
                detail = self._extract_error_detail(response)
                if "not found" in detail.lower():
                    raise LLMError(
                        f"Ollama model '{self._settings.model_name}' is not installed. "
                        f"Run: ollama pull {self._settings.model_name}. "
                        f"Details: {detail}",
                        retryable=False,
                    )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError() from exc
        except LLMError:
            raise
        except httpx.HTTPError as exc:
            raise LLMError(f"Ollama request failed: {exc}", retryable=True) from exc

        data = response.json()
        message = data.get("message", {})
        content = (message.get("content") or "").strip()
        thinking = (message.get("thinking") or "").strip()
        content = self._select_json_text(content, thinking)

        # Debug dump for wizard failures ("No valid JSON object found").
        try:
            from pathlib import Path

            dump_dir = Path(__file__).resolve().parents[3] / "case_capture"
            dump_dir.mkdir(exist_ok=True)
            dump_path = dump_dir / "last_llm_response.json"
            dump_path.write_text(
                json.dumps(
                    {
                        "model": self._settings.model_name,
                        "done_reason": data.get("done_reason"),
                        "content_len": len(message.get("content") or ""),
                        "thinking_len": len(message.get("thinking") or ""),
                        "selected_len": len(content),
                        "content_head": (message.get("content") or "")[:500],
                        "content_full": message.get("content") or "",
                        "thinking_head": (message.get("thinking") or "")[:800],
                        "selected_head": content[:800],
                        "selected_full": content,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as dump_exc:  # noqa: BLE001
            logger.warning("Could not write LLM dump: %s", dump_exc)

        # A reasoning model draws its thoughts from the same budget as its answer, so a
        # long deliberation can end the turn before a single character of JSON is written.
        # Naming that here saves the caller from a parse error against an essay.
        if not (message.get("content") or "").strip() and thinking and "{" not in thinking:
            raise LLMError(
                f"{self._settings.model_name} spent its whole {config.max_tokens}-token "
                f"budget on reasoning ({len(thinking)} characters of it, finish reason "
                f"{data.get('done_reason')!r}) and wrote no JSON. Lower the thinking level "
                "(ollama.think: low) or raise generation.max_tokens in config/llm.yaml.",
                retryable=True,
            )
        if not content:
            raise LLMError("Ollama returned empty content", retryable=True)

        return LLMResponse(
            content=content,
            model=self._settings.model_name,
            provider=self.provider_name,
            finish_reason=data.get("done_reason"),
            raw=data,
        )

    @staticmethod
    def _looks_like_package_json(text: str) -> bool:
        """True only for an actual JSON object, not prose that names the fields."""
        if not text:
            return False
        stripped = text.lstrip()
        brace = 0 if stripped.startswith("{") else stripped.find("{")
        if brace < 0 or brace > 120:
            return False
        body = stripped[brace : brace + 4000]
        return bool(
            re.search(r'"welcome_message"\s*:', body)
            or re.search(r'"daily_itinerary"\s*:', body)
            or re.search(r'"trip_title"\s*:', body)
        )

    @staticmethod
    def _select_json_text(content: str, thinking: str) -> str:
        """Prefer the content channel whenever it is real package JSON.

        gpt-oss often fills `thinking` with a long essay that mentions field
        names. That must never outrank a JSON object sitting in `content`.
        """
        content = (content or "").strip()
        thinking = (thinking or "").strip()
        if OllamaProvider._looks_like_package_json(content):
            return content
        if OllamaProvider._looks_like_package_json(thinking):
            logger.warning("Using thinking channel for JSON (content was not package JSON)")
            return thinking
        if "{" in content:
            return content
        if "{" in thinking:
            logger.warning("Using thinking channel (only channel with a JSON brace)")
            return thinking
        return content or thinking

    async def health_check(self) -> bool:
        client = await self._get_client()
        base = self._settings.ollama_base_url.rstrip("/")
        try:
            response = await client.get(f"{base}/api/tags", timeout=5.0)
            if response.status_code != 200:
                return False
            models = response.json().get("models", [])
            installed = {item.get("name", "") for item in models}
            model = self._settings.model_name
            return any(name == model or name.startswith(f"{model}:") for name in installed)
        except httpx.HTTPError:
            logger.warning("Ollama health check failed")
            return False

    @staticmethod
    def _extract_error_detail(response: httpx.Response) -> str:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                return str(payload.get("error", response.text))
        except ValueError:
            pass
        return response.text

    async def close(self) -> None:
        """Close the HTTP client if owned by this provider."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
