"""Prompt loading and single-shot package prompt rendering."""

from __future__ import annotations

import re
from pathlib import Path

from app.config.settings import AppSettings, get_app_settings

_VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")
_SECTION_SEPARATOR = "\n\n---\n\n"

# Canonical 3-file pack under prompts/
PACKAGE_PROMPT_FILES = (
    "01_role_and_rules.md",
    "02_retriever.md",
    "03_output_schema.md",
)


class PromptService:
    """Loads prompt templates from the prompts directory and renders variables."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self._settings = settings or get_app_settings()

    @property
    def prompts_dir(self) -> Path:
        return self._settings.prompts_dir

    def load(self, template_name: str) -> str:
        """Load raw template content by filename."""
        path = self.prompts_dir / template_name
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {path}")
        return path.read_text(encoding="utf-8")

    def compose_sections(self, section_names: list[str]) -> str:
        """Join ordered prompt section files into one system prompt."""
        if not section_names:
            raise ValueError("At least one prompt section is required")
        parts = [self.load(name).strip() for name in section_names]
        return _SECTION_SEPARATOR.join(parts)

    def render_variables(self, content: str, **variables: str) -> str:
        """Substitute {{VAR}} placeholders. Missing keys raise KeyError."""

        def replacer(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in variables:
                raise KeyError(f"Missing template variable: {key}")
            return variables[key]

        return _VARIABLE_PATTERN.sub(replacer, content)

    def render_sections(self, section_names: list[str], **variables: str) -> str:
        """Compose sections, then substitute {{VAR}} placeholders."""
        content = self.compose_sections(section_names)
        return self.render_variables(content, **variables)

    def build_package_prompt(self, **variables: str) -> str:
        """
        Build one merged prompt from the 3-file pack under ``prompts/``:

        role+rules + retriever guide + output schema + LIVE INPUTS.
        The LLM must return the full package JSON in a single response.
        """
        parts = [
            self.load("01_role_and_rules.md").strip(),
            self.load("02_retriever.md").strip(),
            self.load("03_output_schema.md").strip(),
            (
                "## LIVE INPUTS (injected once)\n"
                "USER_PROFILE:\n{{user_profile}}\n\n"
                "TRIP_PREFERENCE:\n{{trip_preferences}}\n\n"
                "RETRIEVED_KNOWLEDGE:\n{{knowledge_context}}"
            ),
        ]
        content = _SECTION_SEPARATOR.join(parts)
        return self.render_variables(content, **variables)

    # Backward-compatible alias used by older call sites/tests.
    def build_task_prompt(self, task_name: str | None = None, **variables: str) -> str:
        """Deprecated alias — always builds the single merged package prompt."""
        _ = task_name
        # Older call sites passed generated_itinerary / trip_details; ignore extras.
        allowed = {
            "user_profile": variables.get("user_profile", "{}"),
            "trip_preferences": variables.get("trip_preferences", "{}"),
            "knowledge_context": variables.get("knowledge_context", "{}"),
        }
        return self.build_package_prompt(**allowed)
