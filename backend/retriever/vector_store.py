"""
ReTour Retriever — VectorStore abstraction
==========================================

A thin interface over the vector DB so it is swappable (Chroma now,
Qdrant/Weaviate later) without rewriting retrieval logic.

Four collections (one per entity_type) — separate retrieval per type is
required by the composite-itinerary rule, and gives sharper per-type BM25.
Each stored record carries: dense vector + metadata (region, category,
hard-filter fields, operational facts for the response, coordinates, nearby).
The sparse (BM25) text is stored as a document field for the BM25 index.

Phase-2a note: query() now explicitly requests `distances`. The collection uses
cosine space, so `similarity = 1 - distance`. This is purely additive — the
returned ordering is unchanged; retrieval simply gains a real relevance signal
to drive a quality cutoff (previously the score was computed then discarded).
"""

from typing import List, Dict, Any, Optional
import chromadb


class VectorStore:
    """Wraps a vector DB. Implementation detail hidden behind add/query/get."""

    def __init__(self, path: Optional[str] = None):
        # persistent if a path is given, else in-memory
        self._client = chromadb.PersistentClient(path=path) if path \
            else chromadb.EphemeralClient()
        self._collections: Dict[str, Any] = {}

    def collection(self, name: str):
        """Get or create a collection (we bring our own vectors, so no
        embedding function is configured on the DB side)."""
        if name not in self._collections:
            self._collections[name] = self._client.get_or_create_collection(
                name=name, metadata={"hnsw:space": "cosine"})
        return self._collections[name]

    def add(self, coll_name: str, ids: List[str], vectors: List[List[float]],
            documents: List[str], metadatas: List[Dict[str, Any]]) -> None:
        """Insert records. `documents` holds the sparse/BM25 text."""
        self.collection(coll_name).add(
            ids=ids, embeddings=vectors,
            documents=documents, metadatas=metadatas)

    def query(self, coll_name: str, vector: List[float], n: int,
              where: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dense ANN query with optional metadata pre-filter (hard filter).
        Requests distances so the caller can derive cosine similarity."""
        return self.collection(coll_name).query(
            query_embeddings=[vector], n_results=n, where=where,
            include=["metadatas", "distances"])

    def get_all(self, coll_name: str) -> Dict[str, Any]:
        """Return all records of a collection (used to build the BM25 index)."""
        return self.collection(coll_name).get(
            include=["documents", "metadatas"])