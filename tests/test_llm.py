"""Tests for LLM provider abstraction."""

from __future__ import annotations

import json

import pytest

from app.config.settings import LLMSettings
from app.core.exceptions import LLMError
from app.core.interfaces.llm import LLMGenerationConfig, LLMMessage, LLMResponse
from app.llm.factory import create_llm_provider
from app.llm.manager import LLMManager


class FakeProvider:
    provider_name = "fake"

    def __init__(self) -> None:
        self.calls = 0

    async def generate(
        self,
        messages: list[LLMMessage],
        config: LLMGenerationConfig,
    ) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            content='{"ok": true}',
            model="fake-model",
            provider="fake",
        )

    async def health_check(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_llm_manager_delegates_to_provider() -> None:
    fake = FakeProvider()
    manager = LLMManager(provider=fake)
    response = await manager.generate([LLMMessage(role="user", content="hello")])
    assert response.content == '{"ok": true}'
    assert fake.calls == 1


def test_select_json_prefers_content_over_thinking_prose() -> None:
    from app.llm.providers.ollama_provider import OllamaProvider

    content = (
        '{"welcome_message":"Welcome","trip_title":"Jordan Escape",'
        '"daily_itinerary":[{"day_number":"1"}]}'
    )
    thinking = (
        "We need to produce a single JSON object with the specified structure. "
        "Must include fields: welcome_message, why_you_will_love_this, trip_title, "
        "trip_description, trip_details, daily_itinerary (3 days), budget_summary."
    )
    selected = OllamaProvider._select_json_text(content, thinking)
    assert selected.startswith("{")
    assert '"welcome_message"' in selected
    assert not selected.startswith("We need")


def test_select_json_uses_thinking_only_when_it_is_real_json() -> None:
    from app.llm.providers.ollama_provider import OllamaProvider

    thinking = '{"welcome_message":"Hi","trip_title":"North","daily_itinerary":[]}'
    selected = OllamaProvider._select_json_text("not json at all", thinking)
    assert selected.startswith("{")
    assert '"trip_title"' in selected


class _ThinkSettings:
    """Minimal stand-in for LLMSettings, carrying only what a request needs."""

    model_name = "gpt-oss:20b-cloud"
    ollama_base_url = "http://localhost:11434"
    ollama_api_path = "/api/chat"
    ollama_num_ctx = 4096
    ollama_num_gpu = None
    ollama_format = "json"
    ollama_keep_alive = "10m"

    def __init__(self, think: bool | str | None = "low") -> None:
        self.ollama_think = think

    def reload(self) -> None:
        return None


def _capturing_provider(response: dict, think: bool | str | None = "low"):
    """An Ollama provider wired to a canned reply, plus the payload it sent."""
    import httpx

    from app.llm.providers.ollama_provider import OllamaProvider

    sent: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.update(json.loads(request.content))
        return httpx.Response(200, json=response)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OllamaProvider(_ThinkSettings(think), client=client), sent


def test_a_thinking_level_reaches_ollama_as_a_level_not_a_flag(tmp_path) -> None:
    """`think: low` must not be flattened to `true`, which means high effort."""
    config = tmp_path / "llm.yaml"
    config.write_text(
        "provider: ollama\n"
        "model:\n  name: gpt-oss:20b-cloud\n"
        "generation:\n  temperature: 0.3\n  top_p: 0.9\n  max_tokens: 2048\n"
        "  timeout_seconds: 60\n  max_retries: 0\n"
        "ollama:\n  base_url: http://localhost:11434\n  api_path: /api/chat\n"
        "  think: LOW\n",
        encoding="utf-8",
    )
    assert LLMSettings(config).ollama_think == "low"


def test_a_boolean_thinking_setting_still_works_for_models_that_honour_it(tmp_path) -> None:
    config = tmp_path / "llm.yaml"
    config.write_text(
        "provider: ollama\n"
        "model:\n  name: qwen3:8b\n"
        "generation:\n  temperature: 0.3\n  top_p: 0.9\n  max_tokens: 2048\n"
        "  timeout_seconds: 60\n  max_retries: 0\n"
        "ollama:\n  base_url: http://localhost:11434\n  api_path: /api/chat\n"
        "  think: false\n",
        encoding="utf-8",
    )
    assert LLMSettings(config).ollama_think is False


@pytest.mark.asyncio
async def test_thinking_travels_as_a_request_field_not_a_sampling_option() -> None:
    provider, sent = _capturing_provider(
        {"done_reason": "stop", "message": {"content": '{"trip_title":"X"}'}}
    )
    await provider.generate(
        [LLMMessage(role="user", content="hi")],
        LLMGenerationConfig(temperature=0.3, top_p=0.9, max_tokens=2048, timeout_seconds=60),
    )
    assert sent["think"] == "low"
    assert "think" not in sent["options"]


@pytest.mark.asyncio
async def test_a_reply_that_is_all_reasoning_and_no_json_says_so() -> None:
    """The budget covers thoughts and answer alike, so exhausting it must be legible."""
    provider, _ = _capturing_provider(
        {
            "done_reason": "length",
            "message": {"content": "", "thinking": "We need to output a package. " * 40},
        }
    )
    with pytest.raises(LLMError) as caught:
        await provider.generate(
            [LLMMessage(role="user", content="hi")],
            LLMGenerationConfig(
                temperature=0.3, top_p=0.9, max_tokens=2048, timeout_seconds=60
            ),
        )
    message = caught.value.message
    assert "reasoning" in message
    assert "max_tokens" in message
    assert caught.value.retryable


@pytest.mark.asyncio
async def test_json_hiding_in_the_thinking_channel_is_still_rescued() -> None:
    provider, _ = _capturing_provider(
        {
            "done_reason": "stop",
            "message": {
                "content": "",
                "thinking": '{"welcome_message":"Hi","trip_title":"North",'
                '"daily_itinerary":[]}',
            },
        }
    )
    response = await provider.generate(
        [LLMMessage(role="user", content="hi")],
        LLMGenerationConfig(temperature=0.3, top_p=0.9, max_tokens=2048, timeout_seconds=60),
    )
    assert '"trip_title"' in response.content


def test_create_ollama_provider_from_config() -> None:
    from pathlib import Path

    config_path = Path(__file__).resolve().parent.parent / "config" / "llm.yaml"
    settings = LLMSettings(config_path)
    provider = create_llm_provider(settings)
    assert provider.provider_name == "ollama"


def test_unsupported_provider_raises() -> None:
    from pathlib import Path
    import yaml

    config_path = Path(__file__).resolve().parent.parent / "config" / "llm.yaml"
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data["provider"] = "unknown_provider"

    class BadSettings:
        provider = "unknown_provider"

    with pytest.raises(LLMError):
        create_llm_provider(BadSettings())  # type: ignore[arg-type]
