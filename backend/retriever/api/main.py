"""
ReTour Retriever — FastAPI application.

- lifespan: build/load the index ONCE at startup (heavy work off the request path).
- POST /api/v1/knowledge/search : wizard -> hierarchical itinerary context.
- GET  /health                  : liveness + whether the index is ready.

Endpoints are declared `def` (not async): the retrieval stack is synchronous
(Chroma, BM25, sentence-transformers). FastAPI runs sync endpoints in a
threadpool, so a blocking search never freezes the event loop.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

from api.config import settings
from api.models import WizardRequest, SearchResponse
from api.service import RetrieverService

_state: dict = {"service": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — build the index once.
    _state["service"] = RetrieverService.load(
        data_dir=settings.data_dir,
        embedder_model=settings.embedder_model,
        index_path=settings.index_path,
        rest_per_poi=settings.rest_per_poi,
        hotels_per_cluster=settings.hotels_per_cluster,
        events_per_cluster=settings.events_per_cluster,
    )
    yield
    _state["service"] = None  # shutdown cleanup


app = FastAPI(title="ReTour Retriever API", version="1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "index_ready": _state["service"] is not None}


@app.post("/api/v1/knowledge/search", response_model=SearchResponse)
def search(req: WizardRequest):
    service = _state["service"]
    if service is None:
        raise HTTPException(status_code=503, detail="Index not ready")
    try:
        return service.search(req.model_dump())
    except Exception as e:  # never leak a stack trace to Alpha
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {e}")
