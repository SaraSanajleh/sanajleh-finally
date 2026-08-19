# RAG

Retrieval is tourism-aware. It is not `query → top 5 documents`, and it is not “dump retriever clusters into the LLM”.

## Pipeline

1. Wizard request is normalized to a tourist profile
2. Context locks **one requested region per day**
3. Each day gets its own retrieval query (region, interests, pace, heat, avoid list)
4. Recall is **geo-gated**: local catalog for that region, plus retriever cards only if they belong there
5. Ranker scores traveler fit, then collapses same-site monuments into one visit
6. Diversity packing avoids four ruins and no forest
7. The itinerary is built from those shortlists. The LLM only writes narrative

## Hard geographic rule

A Jerash day can only schedule Jerash catalog items. An Irbid card with a Jerash-sounding name still cannot score there.

Jerash Hippodrome + South Theater + the archaeological site are **one ticket**, not three stops.

## Indexing

The Brain plans from the tourism catalog even if the retriever is down.

```bash
cd backend/retriever
python index_data.py
```

## What is retrieved

- POIs, restaurants, hotels from the catalog, ranked per locked day
- SME matching is a separate layer: one guide and one operator for the whole package
