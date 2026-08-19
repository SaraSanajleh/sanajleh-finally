"""Prompt loading abstraction — supports future Prompt Library."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PromptLoader(Protocol):
    """Contract for loading and rendering prompt templates."""

    def load(self, template_name: str) -> str:
        """Load raw template content by name."""
        ...

    def render(self, template_name: str, **variables: str) -> str:
        """Load and substitute {{VAR}} placeholders in a template."""
        ...
