"""Assemble planner prompts from isolated sections and structured objects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config.settings import AppSettings, get_app_settings
from app.context.models import PlanningContext
from app.planning.profile import TouristProfile
from app.retrieval.knowledge import RetrievedKnowledge
from app.sme.models import SMEMatch


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


class PromptBuilder:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self._settings = settings or get_app_settings()
        self._root = self._settings.project_root / "prompts" / "v2"

    def system_prompt(self) -> str:
        return "\n\n".join(
            [
                _read(self._root / "system.md"),
                _read(self._root / "planning_rules.md"),
                _read(self._root / "output_contract.md"),
            ]
        )

    def user_prompt(
        self,
        *,
        profile: TouristProfile,
        context: PlanningContext,
        knowledge: RetrievedKnowledge,
        smes: list[SMEMatch],
        wizard_json: dict[str, Any],
        locked_package: dict[str, Any] | None = None,
    ) -> str:
        sme_cards = [match.prompt_card() for match in smes[:2]]
        sections = [
            "## Wizard request",
            _json(wizard_json),
            "## Why context changed this plan",
            _json([item.model_dump(mode="json") for item in context.decisions]),
            "## Locked day regions",
            _json([item.model_dump(mode="json") for item in context.day_intents]),
            "## Ranked knowledge for each locked day",
            _json(knowledge.prompt_dict(self._settings).get("day_shortlists")),
            "## Trip SME team (one guide + one operator for the whole package)",
            _json(sme_cards or {"note": "No relevant SMEs matched. Do not invent any."}),
        ]
        if locked_package:
            sections.extend(
                [
                    "## Locked itinerary (IDs, names, regions, SMEs are frozen)",
                    _json(locked_package),
                    "## Output instruction",
                    (
                        "Return the same JSON shape. You may improve trip_title, welcome_message, "
                        "trip.summary, each day's theme/summary, and matching item descriptions/reasons. "
                        "Do not add, remove, replace, or rename any item_id or sme_id. "
                        "Do not move a place into another day's region. "
                        "Do not change time, end_time, duration_minutes, or estimated_cost — "
                        "those already come from the catalog."
                    ),
                ]
            )
        else:
            sections.append("## Output instruction\nProduce the Tourism Package JSON now.")
        return "\n\n".join(sections)

    def repair_prompt(self, errors: list[str], previous: str) -> str:
        return (
            "The previous JSON failed validation. Return a corrected JSON object only.\n"
            f"Errors:\n{_json(errors)}\n\nPrevious JSON:\n{previous[:12000]}"
        )
