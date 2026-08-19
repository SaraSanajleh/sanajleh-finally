"""Write a single-shot composed LLM prompt preview to prompts/_composed_preview.md."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.prompt_service import PromptService

OUT = Path("prompts/_composed_preview.md")


def main() -> None:
    svc = PromptService()
    sample_profile = {
        "mode": "build",
        "trip": {"duration": "2", "totalBudget": 600, "preferredLanguage": "English"},
    }
    sample_prefs = {
        "interests": ["history"],
        "tripPace": "Balanced",
        "mustVisit": ["Petra"],
    }
    sample_knowledge = {
        "duration_days": 2,
        "clusters": [
            {
                "cluster_id": 0,
                "theme": "Sample theme",
                "summary": "Sample summary",
                "pois": [],
                "hotels": [],
                "events": [],
            }
        ],
        "meta": {"rag_status": "ok", "unsupported": [], "places_to_avoid": ""},
    }
    rendered = svc.build_package_prompt(
        user_profile=json.dumps(sample_profile, indent=2, ensure_ascii=False),
        trip_preferences=json.dumps(sample_prefs, indent=2, ensure_ascii=False),
        knowledge_context=json.dumps(sample_knowledge, indent=2, ensure_ascii=False),
    )
    OUT.write_text(rendered, encoding="utf-8")
    print(f"Wrote {OUT} ({len(rendered)} chars)")


if __name__ == "__main__":
    main()
