"""Generate a 2-day package with RAG (in-process)."""

from __future__ import annotations

import asyncio
import json
import time

from app.agents.package_builder_agent import PackageBuilderAgent
from app.config.settings import get_app_settings
from app.llm.manager import LLMManager
from app.schemas.request.package_request import PackageRequest
from app.services.prompt_service import PromptService
from app.services.retriever_client import HttpRetrieverClient
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST


async def main() -> None:
    payload = json.loads(json.dumps(VALID_PACKAGE_REQUEST))
    payload["trip"]["duration"] = "2"
    payload["trip"]["totalBudget"] = 600
    request = PackageRequest.model_validate(payload)

    settings = get_app_settings()
    knowledge = HttpRetrieverClient(settings=settings)
    agent = PackageBuilderAgent(
        llm_manager=LLMManager(),
        prompt_service=PromptService(),
        knowledge=knowledge,
        settings=settings,
    )

    print("CASE: couple anniversary | 2 days | 600 JOD | Petra/Wadi Rum/Dead Sea", flush=True)
    kn = await knowledge.search_for_itinerary(request)
    print(
        "RAG:",
        kn.get("meta", {}).get("rag_status"),
        "clusters=",
        len(kn.get("clusters") or []),
        flush=True,
    )
    for c in kn.get("clusters") or []:
        print("  theme:", c.get("theme"), flush=True)

    print("Generating...", flush=True)
    t0 = time.time()
    package, metadata, _knowledge = await agent.generate_package(request)
    elapsed = time.time() - t0
    data = package.model_dump(mode="json")
    print(f"OK in {elapsed:.1f}s | model={metadata.model} | retries={metadata.retries}", flush=True)
    print("title:", data.get("trip_title"), flush=True)
    for day in data.get("daily_itinerary") or []:
        acts = [a.get("activity_title") for a in (day.get("activities") or [])]
        print(f"  day {day.get('day_number')}: {day.get('day_title')} | {acts}", flush=True)
        alts = day.get("activity_alternatives") or []
        if alts:
            print(f"    alts: {len(alts)}", flush=True)
        times = [
            f"{a.get('start_time')}-{a.get('end_time')}"
            for a in (day.get("activities") or [])
            if a.get("start_time") or a.get("end_time")
        ]
        if times:
            print(f"    times: {times[:4]}", flush=True)
    print("total:", (data.get("budget_summary") or {}).get("total_estimated_cost"), flush=True)

    out = "last_rag_package.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(
            {"success": True, "package": data, "metadata": metadata.model_dump(mode="json")},
            f,
            ensure_ascii=False,
            indent=2,
        )
    print("saved", out, flush=True)
    await knowledge.close()
    await agent._llm.close()


if __name__ == "__main__":
    asyncio.run(main())
