"""One-off smoke: 2-day Jerash/Ajloun package via in-process agent."""

from __future__ import annotations

import asyncio
import json
import time
import traceback
from pathlib import Path

from app.api.dependencies import get_knowledge_provider, get_package_builder_agent
from app.config.settings import get_llm_settings
from app.schemas.request.package_request import PackageRequest

PAYLOAD = {
    "mode": "build",
    "requestedAt": "2026-08-04T13:00:00.000Z",
    "trip": {
        "startDate": "2026-09-10",
        "duration": "2",
        "arrivalAirport": "AMM",
        "totalBudget": 600,
        "preferredLanguage": "English",
        "preferredRegions": ["Jerash", "Ajloun"],
    },
    "travelers": {
        "adults": 2,
        "children": 0,
        "childrenAges": [],
        "seniors": 0,
        "groupType": "couple",
        "accessibilityNeeds": [],
    },
    "preferences": {
        "interests": ["history", "food", "nature"],
        "tripPace": "Balanced",
        "activityLevel": "Moderate",
        "mustVisit": ["Jerash"],
        "placesToAvoid": "Petra, Wadi Rum",
    },
    "accommodation": {"type": "boutique", "rating": "4 star"},
    "dining": {"cuisine": ["Local Jordanian"]},
    "extras": {
        "specialOccasion": "None",
        "smePreferences": ["Family-owned Businesses"],
        "aiPriority": "authentic",
        "freeText": "North Jordan focus: Jerash and Ajloun. Avoid Petra and Wadi Rum.",
    },
}


async def main() -> int:
    llm = get_llm_settings()
    print(
        f"LLM model={llm.model_name} think={llm.ollama_think} "
        f"max_tokens={llm.max_tokens} num_ctx={llm.ollama_num_ctx}"
    )
    knowledge = get_knowledge_provider()
    print(f"knowledge={type(knowledge).__name__}")
    req = PackageRequest.model_validate(PAYLOAD)

    rag = await knowledge.search_for_itinerary(req)
    clusters = rag.get("clusters") or []
    meta = rag.get("meta") or {}
    print(
        f"RAG status={meta.get('rag_status')} compacted={meta.get('compacted')} "
        f"clusters={len(clusters)}"
    )
    for cluster in clusters[:8]:
        pois = cluster.get("pois") or []
        hotels = cluster.get("hotels") or []
        print(
            f"  cluster {cluster.get('cluster_id')}: theme={cluster.get('theme')!r} "
            f"pois={len(pois)} hotels={len(hotels)}"
        )

    agent = get_package_builder_agent()
    t0 = time.perf_counter()
    try:
        package, gen_meta, _knowledge = await agent.generate_package(req)
    except Exception as exc:  # noqa: BLE001
        print("GENERATE_FAILED", type(exc).__name__, exc)
        traceback.print_exc()
        Path("case_smoke_result.json").write_text(
            json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return 1

    elapsed = time.perf_counter() - t0
    data = package.model_dump(mode="json")
    days = data.get("daily_itinerary") or []
    blob = json.dumps(data, ensure_ascii=False).lower()
    bad = [w for w in ("petra", "wadi rum") if w in blob]
    good = [w for w in ("jerash", "ajloun") if w in blob]
    summary = {
        "status": "succeeded",
        "elapsed_s": round(elapsed, 1),
        "metadata": gen_meta.model_dump(mode="json"),
        "rag_clusters": len(clusters),
        "day_count": len(days),
        "welcome": (data.get("welcome_message") or "")[:180],
        "days": [
            {
                "day": d.get("day_number") or d.get("day"),
                "title": d.get("day_title"),
                "activities": [
                    a.get("activity_title") or a.get("name")
                    for a in (d.get("activities") or [])
                ],
            }
            for d in days
        ],
        "mentions_jerash_or_ajloun": good,
        "mentions_avoid_places": bad,
    }
    Path("case_smoke_result.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("==== RESULT ====")
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
