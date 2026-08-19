"""
ReTour Retriever — Station B4: Indexer
======================================

Connects all earlier stations into a searchable index:

    load 4 JSON files
      -> normalize_entity            (B1)
      -> build_texts -> dense/sparse (B2)
      -> compute_nearby (corpus)     (B3)
      -> 4 collections in the VectorStore, one per entity_type
         each record = dense vector + sparse(BM25) doc + metadata

Metadata carried per record (for hard filter + response):
    region, category, hard-filter fields (accessibility, dietary_options,
    suitable_for), operational facts (returned to the agent), coordinates,
    and the computed `nearby`.

Works on ANY corpus size (no fixed count assumed).
"""

import json
from typing import List, Dict, Any

from normalize import normalize_entity, region_key
from embedding_text import build_texts
from geo import compute_nearby
from embedder import Embedder
from vector_store import VectorStore

# entity_type -> collection name
_COLLECTION = {"poi": "pois", "hotel": "hotels",
               "restaurant": "restaurants", "event": "events"}

# metadata kept flat for filtering/response (Chroma metadata must be scalars,
# so lists are joined; nested/operational blocks are JSON-encoded).
_HARD_FIELDS = ("accessibility", "dietary_options", "suitable_for")


def _load_entities(paths: List[str]) -> List[dict]:
    """Load entities from the 4 JSON files (each file = array of one type)."""
    entities = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        entities.extend(data if isinstance(data, list) else [data])
    return entities


def _flatten_meta(entity: dict, nearby: dict) -> Dict[str, Any]:
    """Build the flat metadata record stored beside the vector.

    Two kinds of fields:
      - FLAT scalars/pipes: used by retrieval for filtering, geo, boosting,
        selection (fast, no JSON parse) — region, category, coords, hard fields,
        themes, cuisine_types, activity_level, occasion_suitability, star_rating.
      - JSON blobs: the rich sub-blocks the RESPONSE exposes to the agent
        (identity/location/experience/context/audience/operation/pricing/nearby).
        The service layer parses these to build the final decision-supporting card.
    """
    idn = entity.get("identity", {}) or {}
    loc = entity.get("location", {}) or {}
    coords = loc.get("coordinates", {}) or {}
    aud = entity.get("audience", {}) or {}
    sem = entity.get("semantic", {}) or {}
    exp = entity.get("experience", {}) or {}
    ctx = entity.get("context", {}) or {}
    region = loc.get("region", "") or ""

    def pipe(xs):
        return "|" + "|".join(xs or []) + "|"

    sr = exp.get("star_rating")
    meta: Dict[str, Any] = {
        # --- flat identity / geo ---
        "entity_type": entity.get("entity_type", ""),
        "name": idn.get("name", "") or "",
        "region": region,
        "region_key": region_key(region),
        "category": idn.get("category", "") or "",
        "lat": coords.get("latitude") if coords.get("latitude") is not None else 0.0,
        "lon": coords.get("longitude") if coords.get("longitude") is not None else 0.0,
        # --- flat hard-filter fields ("|a|b|") ---
        **{f: pipe(aud.get(f, [])) for f in _HARD_FIELDS},
        # --- flat ranking/boost signals (fast access, no JSON parse) ---
        "themes": pipe(sem.get("themes", [])),
        "cuisine_types": pipe(exp.get("cuisine_types", [])),
        "activity_level": (exp.get("activity_level", "") or "").strip(),
        "occasion_suitability": pipe(aud.get("occasion_suitability", [])),
        "star_rating": sr if isinstance(sr, (int, float)) else 0,
        # --- rich JSON blobs for the response contract ---
        "identity_json": json.dumps(idn, ensure_ascii=False),
        "location_json": json.dumps(loc, ensure_ascii=False),
        "experience_json": json.dumps(exp, ensure_ascii=False),
        "context_json": json.dumps(ctx, ensure_ascii=False),
        "audience_json": json.dumps(aud, ensure_ascii=False),
        "operation_json": json.dumps(entity.get("operation", {}), ensure_ascii=False),
        "pricing_json": json.dumps(entity.get("pricing", {}), ensure_ascii=False),
        "nearby_json": json.dumps(nearby, ensure_ascii=False),
    }
    return meta


def build_index(json_paths: List[str], embedder: Embedder,
                store: VectorStore) -> VectorStore:
    """Run the full ingestion pipeline and populate the store."""
    raw = _load_entities(json_paths)

    # B1: normalize every entity
    entities = [normalize_entity(e) for e in raw]

    # B3: nearby over the WHOLE corpus, once
    nearby_map = compute_nearby(entities, k=5)

    # group by collection
    grouped: Dict[str, List[dict]] = {c: [] for c in _COLLECTION.values()}
    for e in entities:
        coll = _COLLECTION.get(e.get("entity_type"))
        if coll:
            grouped[coll].append(e)

    # index each collection
    for coll_name, items in grouped.items():
        if not items:
            continue
        ids, dense_texts, sparse_texts, metas = [], [], [], []
        for e in items:
            eid = e.get("id")
            dense_t, sparse_t = build_texts(e)   # B2
            ids.append(eid)
            dense_texts.append(dense_t)
            sparse_texts.append(sparse_t)
            metas.append(_flatten_meta(e, nearby_map.get(eid, {})))

        vectors = embedder.encode(dense_texts)   # dense channel
        # `documents` stores the sparse text -> used to build BM25 in B5
        store.add(coll_name, ids=ids, vectors=vectors,
                  documents=sparse_texts, metadatas=metas)

    return store