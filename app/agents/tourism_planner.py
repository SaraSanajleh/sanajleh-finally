"""Central Tourism Planning Agent — one planner, multiple internal layers."""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError

from app.config.settings import AppSettings, get_app_settings
from app.context.builder import build_planning_context
from app.core.exceptions import LLMError, LLMResponseParseError, PackageGenerationError
from app.core.interfaces.llm import LLMMessage
from app.llm.manager import LLMManager
from app.observability.trace import GenerationTrace
from app.planning.itinerary import build_locked_package, overlay_narrative
from app.planning.profile import normalize_tourist_profile
from app.planning.route import apply_open_trip_evidence
from app.prompts.builder import PromptBuilder
from app.retrieval.composer import compose_trip_knowledge
from app.schemas.request.package_request import PackageRequest
from app.schemas.response.package_response import (
    BrainTrace,
    PackageGenerationMetadata,
    RagEvaluationSummary,
    TourismPackage,
)
from app.services.case_capture import build_rag_preview, save_generation_case
from app.services.retriever_client import (
    NullTourismKnowledgeProvider,
    TourismKnowledgeProvider,
)
from app.sme.loader import load_sme_catalog
from app.sme.matcher import select_package_smes, sme_catalog_index
from app.utils.logging import get_logger
from app.validation.package import (
    apply_profile_facts,
    assert_package_ready,
    ground_and_repair,
    parse_package_json,
    validate_schema,
)

logger = get_logger(__name__)

StageCallback = Callable[[str, str], Any]


class _FastNarrativeOut(BaseModel):
    trip_title: str = ""
    welcome_message: str = ""
    trip_summary: str = ""
    day_summaries: list[str] = Field(default_factory=list)


class TourismPlannerAgent:
    """Wizard → Context + RAG + SME → GPT-OSS planner → validated package."""

    def __init__(
        self,
        llm_manager: LLMManager,
        knowledge: TourismKnowledgeProvider | None = None,
        settings: AppSettings | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self._llm = llm_manager
        self._knowledge = knowledge or NullTourismKnowledgeProvider()
        self._settings = settings or get_app_settings()
        self._prompts = prompt_builder or PromptBuilder(self._settings)

    async def generate_package(
        self,
        request: PackageRequest,
        on_stage: StageCallback | None = None,
    ) -> tuple[TourismPackage, PackageGenerationMetadata, dict[str, Any]]:
        started = time.perf_counter()
        trace = GenerationTrace()
        retries = 0
        stage_started = started
        fast_mode = bool(self._settings.planner_fast_mode)
        fast_polish = bool(self._settings.planner_fast_polish)
        trace.planner_fast_mode = fast_mode
        trace.planner_fast_polish = fast_polish
        logger.info(
            "Planner mode: fast_mode=%s fast_polish=%s",
            fast_mode,
            fast_polish,
        )

        async def stage(key: str, label: str) -> None:
            nonlocal stage_started
            elapsed_ms = (time.perf_counter() - stage_started) * 1000
            if trace.stages:
                trace.add(trace.stages[-1], elapsed_ms=elapsed_ms)
            stage_started = time.perf_counter()
            trace.add(key)
            if on_stage:
                result = on_stage(key, label)
                if hasattr(result, "__await__"):
                    await result

        try:
            await stage("normalize", "Understanding your trip")
            profile = normalize_tourist_profile(request)
            trace.profile = {
                "duration_days": profile.duration_days,
                "regions": profile.preferred_regions,
                "interests": profile.interests,
            }

            await stage("knowledge", "Retrieving Jordan tourism knowledge")
            raw_knowledge = await self._knowledge.search_for_itinerary(request)
            profile, inferred_dests = apply_open_trip_evidence(profile, raw_knowledge)
            trace.profile["regions"] = profile.preferred_regions or [
                label for label, _, _ in inferred_dests
            ]

            await stage("context", "Building planning context")
            context = await build_planning_context(
                profile, self._settings, inferred_dests=inferred_dests
            )
            logger.info(
                "Planning context ready: days=%s regions=%s",
                profile.duration_days,
                [intent.region_key for intent in context.day_intents],
            )

            knowledge = compose_trip_knowledge(raw_knowledge, profile, context, self._settings)
            trace.knowledge_counts = {
                "pois": len(knowledge.pois),
                "restaurants": len(knowledge.restaurants),
                "hotels": len(knowledge.hotels),
                "status": 1 if knowledge.status == "ok" else 0,
            }

            await stage("sme", "Matching one guide and one operator")
            load_sme_catalog()
            route_keys = [
                key
                for intent in context.day_intents
                for key in (intent.region_key, intent.overnight_key, getattr(intent, "paired_key", ""))
                if key
            ]
            sme_matches = select_package_smes(profile, self._settings, route_keys=route_keys)
            sme_index = sme_catalog_index()
            trace.sme_counts = {
                "catalog": len(sme_index),
                "matched": len(sme_matches),
                "guides": sum(1 for m in sme_matches if m.record.sme_type == "tour_guide"),
                "operators": sum(1 for m in sme_matches if m.record.sme_type == "tour_operator"),
            }

            await stage(
                "plan",
                "Deterministic fast planning" if fast_mode else "Locking the itinerary",
            )
            skeleton = build_locked_package(profile, context, knowledge, sme_matches)

            package: TourismPackage | None = None
            last_error = "unknown"
            raw_text = ""
            if fast_mode:
                package = apply_profile_facts(skeleton, profile)
                package, _ = ground_and_repair(
                    package, profile, knowledge, sme_index, sme_matches
                )
                assert_package_ready(package, profile)
                if fast_polish:
                    await stage("polish", "Fast narrative polish")
                    package = await self._polish_fast_narrative(
                        package=package,
                        profile=profile,
                        context=context,
                        knowledge=knowledge,
                    )
            else:
                system = self._prompts.system_prompt()
                user = self._prompts.user_prompt(
                    profile=profile,
                    context=context,
                    knowledge=knowledge,
                    smes=sme_matches,
                    wizard_json=request.model_dump(mode="json"),
                    locked_package=skeleton.model_dump(mode="json"),
                )
                trace.prompt_chars = len(system) + len(user)
                logger.info(
                    "Planner prompt ready: chars=%s pois=%s restaurants=%s hotels=%s smes=%s",
                    trace.prompt_chars,
                    len(knowledge.pois),
                    len(knowledge.restaurants),
                    len(knowledge.hotels),
                    len(sme_matches),
                )

                for attempt in range(1, 4):
                    retries = attempt - 1
                    messages = [LLMMessage(role="user", content=user)]
                    if attempt > 1 and raw_text:
                        messages.append(
                            LLMMessage(
                                role="user",
                                content=self._prompts.repair_prompt([last_error], raw_text),
                            )
                        )
                    try:
                        response = await self._llm.generate(
                            messages,
                            system_prompt=system,
                            max_tokens=self._llm.max_tokens,
                        )
                        raw_text = response.content
                        payload = parse_package_json(raw_text)
                        drafted = validate_schema(payload)
                        package = overlay_narrative(skeleton, drafted)
                        package = apply_profile_facts(package, profile)
                        package, repair_errors = ground_and_repair(
                            package, profile, knowledge, sme_index, sme_matches
                        )
                        if repair_errors and attempt < 3:
                            last_error = "; ".join(repair_errors)
                            continue
                        assert_package_ready(package, profile)
                        break
                    except (LLMResponseParseError, LLMError, PackageGenerationError) as exc:
                        last_error = str(exc)
                        logger.warning("Planner attempt %s failed: %s", attempt, exc)
                    except Exception as exc:  # noqa: BLE001
                        last_error = str(exc)
                        logger.warning("Planner attempt %s failed: %s", attempt, exc)

            if package is None:
                package = apply_profile_facts(skeleton, profile)
                package, _ = ground_and_repair(
                    package, profile, knowledge, sme_index, sme_matches
                )
                assert_package_ready(package, profile)

            await stage("validate", "Validating the package")
            trace.validation = {
                "status": package.status,
                "days": len(package.days),
                "warnings": len(package.warnings),
                "constraint_status": package.planning.constraint_status.status,
            }

            debug: dict[str, Any] = {
                "duration_days": raw_knowledge.get("duration_days"),
                "clusters": raw_knowledge.get("clusters") or [],
                "meta": dict(raw_knowledge.get("meta") or {}),
                "sme_candidates": [m.prompt_card() for m in sme_matches],
                "context": context.prompt_dict(),
                "trace": trace.model_dump(mode="json"),
            }
            debug["meta"]["rag_status"] = knowledge.status
            debug["meta"]["source"] = (raw_knowledge.get("meta") or {}).get("source")

            rag_preview = build_rag_preview(debug)
            case_id = save_generation_case(
                request_payload=request.model_dump(mode="json"),
                knowledge=debug,
                package=package.model_dump(mode="json"),
                metadata={
                    "model": self._llm.model_name,
                    "provider": self._llm.provider_name,
                    "mode": request.mode.value,
                    "retries": retries,
                },
            )

            metadata = PackageGenerationMetadata(
                model=self._llm.model_name,
                provider=self._llm.provider_name,
                mode=request.mode.value,
                latencyMs=round((time.perf_counter() - started) * 1000, 1),
                retries=retries,
                caseId=case_id,
                rag=RagEvaluationSummary.model_validate(rag_preview),
                trace=BrainTrace.model_validate(trace.public_dict()),
            )
            await stage("done", "Package ready")
            if trace.stages:
                trace.add(trace.stages[-1], elapsed_ms=(time.perf_counter() - stage_started) * 1000)
            logger.info("Planner stage timings (ms): %s", trace.stage_ms)
            return package, metadata, debug
        except (LLMError, LLMResponseParseError, PackageGenerationError):
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Tourism planner failed")
            raise PackageGenerationError(str(exc) or "Package generation failed") from exc

    async def _polish_fast_narrative(
        self,
        *,
        package: TourismPackage,
        profile,
        context,
        knowledge,
    ) -> TourismPackage:
        """Optional fast copy pass: deterministic itinerary stays locked."""
        data = package.model_dump(mode="python")
        request_payload = {
            "trip_title": data.get("trip_title"),
            "welcome_message": data.get("welcome_message"),
            "trip_summary": (data.get("trip") or {}).get("summary"),
            "day_summaries": [day.get("summary", "") for day in data.get("days", [])],
        }
        prompt = (
            "Rewrite only short marketing text for this locked Jordan itinerary.\n"
            "Rules:\n"
            "- Keep itinerary data unchanged (days/items/times/IDs/costs/regions).\n"
            "- Return valid JSON only with keys: trip_title, welcome_message, trip_summary, day_summaries.\n"
            "- day_summaries length must equal input length.\n"
            "- Keep each summary concise (max 1 sentence).\n"
            f"- Language: {profile.preferred_language}\n\n"
            "Current values:\n"
            f"{json.dumps(request_payload, ensure_ascii=False)}\n\n"
            "Context hints:\n"
            f"{json.dumps([d.model_dump(mode='json') for d in context.decisions[:5]], ensure_ascii=False)}\n"
            f"{json.dumps({'knowledge_status': knowledge.status}, ensure_ascii=False)}"
        )
        try:
            response = await self._llm.generate(
                [LLMMessage(role="user", content=prompt)],
                max_tokens=min(900, self._llm.max_tokens),
            )
            parsed = _FastNarrativeOut.model_validate(parse_package_json(response.content))
        except (LLMError, LLMResponseParseError, ValidationError, ValueError):
            return package

        if parsed.trip_title:
            data["trip_title"] = parsed.trip_title
            data["trip"]["title"] = parsed.trip_title
        if parsed.welcome_message:
            data["welcome_message"] = parsed.welcome_message
        if parsed.trip_summary:
            data["trip"]["summary"] = parsed.trip_summary
        if parsed.day_summaries:
            for idx, summary in enumerate(parsed.day_summaries):
                if idx >= len(data.get("days", [])):
                    break
                if summary:
                    data["days"][idx]["summary"] = summary
        return TourismPackage.model_validate(data)
