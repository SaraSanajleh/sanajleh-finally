"""Tests for prompt loading service — single-shot 3-file pack."""

from __future__ import annotations

import pytest

from app.services.prompt_service import PACKAGE_PROMPT_FILES, PromptService


def test_prompt_loads_three_file_pack() -> None:
    service = PromptService()
    role = service.load("01_role_and_rules.md")
    assert "ReTour AI Brain" in role
    assert "single" in role.lower() or "one complete package" in role.lower()
    assert "<!--BEGIN_TASK" not in role
    assert service.load("02_retriever.md")
    assert service.load("03_output_schema.md")
    assert PACKAGE_PROMPT_FILES == (
        "01_role_and_rules.md",
        "02_retriever.md",
        "03_output_schema.md",
    )


def test_prompt_compose_sections_is_three_file_pack() -> None:
    service = PromptService()
    sections = service._settings.package_generation_sections
    assert sections == [
        "01_role_and_rules.md",
        "02_retriever.md",
        "03_output_schema.md",
    ]
    composed = service.compose_sections(sections)
    assert "SHARED RULES" in composed
    assert "Evidence Package" in composed or "RETRIEVED_KNOWLEDGE" in composed
    assert "Final Assembled Package" in composed or "welcome_message" in composed


def test_build_package_prompt_substitutes_variables() -> None:
    service = PromptService()
    rendered = service.build_package_prompt(
        user_profile='{"trip":{"duration":"2"}}',
        trip_preferences='{"interests":["history"]}',
        knowledge_context='{"clusters":[]}',
    )
    assert "{{user_profile}}" not in rendered
    assert "{{knowledge_context}}" not in rendered
    assert '{"trip":{"duration":"2"}}' in rendered
    assert '{"clusters":[]}' in rendered
    assert rendered.count('{"clusters":[]}') == 1
    assert "LIVE INPUTS" in rendered
    assert "SHARED RULES" in rendered
    assert "ITINERARY RULES" in rendered
    assert "welcome_message" in rendered


def test_build_package_prompt_missing_variable_raises() -> None:
    service = PromptService()
    with pytest.raises(KeyError):
        service.build_package_prompt(user_profile="{}")


def test_prompt_compose_sections_empty_list_raises() -> None:
    service = PromptService()
    with pytest.raises(ValueError):
        service.compose_sections([])
