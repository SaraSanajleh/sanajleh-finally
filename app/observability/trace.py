"""Collect a structured generation trace without exposing prompts in the public API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GenerationTrace(BaseModel):
    stages: list[str] = Field(default_factory=list)
    stage_ms: dict[str, float] = Field(default_factory=dict)
    profile: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    knowledge_counts: dict[str, int] = Field(default_factory=dict)
    sme_counts: dict[str, int] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)
    prompt_chars: int = 0
    planner_fast_mode: bool = False
    planner_fast_polish: bool = False

    def add(self, stage: str, *, elapsed_ms: float | None = None) -> None:
        self.stages.append(stage)
        if elapsed_ms is not None:
            self.stage_ms[stage] = round(elapsed_ms, 1)

    def public_dict(self) -> dict[str, Any]:
        return {
            "stages": self.stages,
            "stage_ms": self.stage_ms,
            "planner_fast_mode": self.planner_fast_mode,
            "planner_fast_polish": self.planner_fast_polish,
            "knowledge_counts": self.knowledge_counts,
            "sme_counts": self.sme_counts,
            "validation": self.validation,
        }
