"""Capture input / RAG / final package for the north Jordan smoke case."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.api.dependencies import get_knowledge_provider, get_package_builder_agent
from app.schemas.request.package_request import PackageRequest

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "case_capture"
OUT_DIR.mkdir(exist_ok=True)

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


def _write(name: str, data: object) -> Path:
    path = OUT_DIR / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


async def main() -> int:
    req = PackageRequest.model_validate(PAYLOAD)
    _write("01_input.json", PAYLOAD)

    knowledge = get_knowledge_provider()
    rag = await knowledge.search_for_itinerary(req)
    rag_path = _write("02_retriever.json", rag)

    # Compact preview of RAG for console
    preview = {
        "duration_days": rag.get("duration_days"),
        "meta": {
            k: (rag.get("meta") or {}).get(k)
            for k in ("rag_status", "compacted", "source", "kept_clusters")
        },
        "clusters": [
            {
                "cluster_id": c.get("cluster_id"),
                "theme": c.get("theme"),
                "poi_count": len(c.get("pois") or []),
                "hotel_count": len(c.get("hotels") or []),
                "poi_names": [
                    ((n.get("poi") or {}).get("name"))
                    for n in (c.get("pois") or [])[:8]
                ],
                "hotel_names": [h.get("name") for h in (c.get("hotels") or [])[:4]],
                "sample_restaurants": [
                    r.get("name")
                    for n in (c.get("pois") or [])[:2]
                    for r in (n.get("restaurants") or [])[:2]
                ],
            }
            for c in (rag.get("clusters") or [])
        ],
    }
    _write("02_retriever_preview.json", preview)

    agent = get_package_builder_agent()
    package, meta, _knowledge = await agent.generate_package(req)
    pkg = package.model_dump(mode="json")
    _write("03_output.json", {"metadata": meta.model_dump(mode="json"), "package": pkg})

    out_preview = {
        "metadata": meta.model_dump(mode="json"),
        "welcome_message": pkg.get("welcome_message"),
        "trip_title": pkg.get("trip_title"),
        "trip_details": pkg.get("trip_details"),
        "days": [
            {
                "day_number": d.get("day_number"),
                "day_title": d.get("day_title"),
                "activities": [
                    {
                        "time": f"{a.get('start_time')}-{a.get('end_time')}",
                        "title": a.get("activity_title"),
                        "location": a.get("location"),
                        "cost": a.get("estimated_cost"),
                    }
                    for a in (d.get("activities") or [])
                ],
            }
            for d in (pkg.get("daily_itinerary") or [])
        ],
        "budget_total": (pkg.get("budget_summary") or {}).get("total_estimated_cost"),
        "explanations": pkg.get("explanations"),
    }
    _write("03_output_preview.json", out_preview)

    print("WROTE", OUT_DIR)
    print("RAG_FILE_BYTES", rag_path.stat().st_size)
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
