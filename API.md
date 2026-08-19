# API

Base prefix: `/api/v1`

## Package generation

`POST /api/v1/packages/generate`

Accepts the existing Wizard `PackageRequest`. Returns a validated `TourismPackage`.

`POST /api/v1/packages/generate/async`

Starts a job. Poll `GET /api/v1/packages/jobs/{jobId}`.

Job payload includes `stage` and `stageLabel` for the generation UI.

## Internal / useful services

`POST /api/v1/knowledge/search` — tourism RAG for a wizard request  
`POST /api/v1/sme/search` — SME matches for a wizard request  
`POST /api/v1/context/build` — structured planning context  

These are also callable from Python:

```python
from app.planning.profile import normalize_tourist_profile
from app.sme.matcher import match_smes
```

## Health

`GET /api/v1/health`  
`GET /api/v1/health/llm`

## Cases

`GET /api/v1/cases`  
`GET /api/v1/cases/{caseId}`

Used for evaluation. Public UI does not show raw prompts.
