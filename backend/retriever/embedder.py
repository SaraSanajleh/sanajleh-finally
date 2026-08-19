"""
ReTour Retriever — Embedder abstraction
=======================================

A thin interface so the embedding model is swappable in one line.
Start with MiniLM (light, fast); swap to BGE-M3 / Qwen later without
touching the rest of the system.

Design decision: the embedding model "sets the ceiling", so it must be
pluggable and chosen by MEASUREMENT (gold queries), not assumption.
"""

from typing import List, Protocol


class Embedder(Protocol):
    """Any embedder exposes encode(texts) -> list[list[float]] and a dim."""
    dim: int
    def encode(self, texts: List[str]) -> List[List[float]]: ...


class MiniLMEmbedder:
    """Local sentence-transformers MiniLM. Runs offline once the model is cached.
    Used both at indexing time (whole corpus) and request time (single query)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(model_name)
        self.dim = self._model.get_sentence_embedding_dimension()

    def encode(self, texts: List[str]) -> List[List[float]]:
        vecs = self._model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vecs]


# Swap target for later (kept as reference; enable when needed):
# class BGEM3Embedder:
#     def __init__(self, model_name="BAAI/bge-m3"):
#         from sentence_transformers import SentenceTransformer
#         self._model = SentenceTransformer(model_name)
#         self.dim = self._model.get_sentence_embedding_dimension()
#     def encode(self, texts): 
#         return [v.tolist() for v in self._model.encode(texts, normalize_embeddings=True)]
