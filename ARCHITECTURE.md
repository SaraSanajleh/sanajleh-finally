# Architecture

ReTour Brain is a single FastAPI application plus a tourism retriever process. It is modular, not a microservice mesh.

## Layers

| Layer | Path | Responsibility |
|---|---|---|
| API | `app/api/routes/` | HTTP only |
| Planning | `app/planning/` | Wizard → `TouristProfile`, geography, constraints |
| Context | `app/context/` | Deterministic planning context, optional weather |
| Retrieval | `app/retrieval/` + `backend/retriever/` | Tourism-aware RAG over POIs, restaurants, hotels |
| SME | `app/sme/` | Load, match, rank, explain guides and operators |
| Prompts | `app/prompts/` + `prompts/v2/` | Structured prompt builder |
| Agent | `app/agents/tourism_planner.py` | One central planner |
| Validation | `app/validation/` | Schema + grounding + repair |
| LLM | `app/llm/` | Provider abstraction. Current model: GPT-OSS |
| UI | `frontend/` | Wizard + itinerary experience |

## Pipeline

1. Validate Wizard `PackageRequest` (unchanged contract)
2. Normalize to `TouristProfile`
3. Build `PlanningContext` with visible decisions and a locked day→region route
4. Compose RAG: day query → geo-gated recall → rank → same-site pack
5. Match **one guide and one operator** for the whole package
6. Build a locked itinerary skeleton from those shortlists
7. GPT-OSS writes title, summaries, and reasons only — it cannot change IDs or regions
8. Overlay narrative, validate, persist the case
9. Return `TourismPackage` to the UI. If the model fails, the skeleton still ships

## Non-negotiable rules

- Never invent POIs, hotels, restaurants, SMEs, prices, hours, or coordinates
- Must-visit is a hard constraint; unmet items get a reason code
- `placesToAvoid` is a hard exclusion
- Tourist relevance outranks commercial promotion
- SME subscription may add a tiny boost only after a relevance threshold

## Extensibility

New datasets, SME types, booking, accounts, and ranking policies can be added behind the same interfaces without replacing the planner.
