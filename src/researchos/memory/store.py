"""Semantic memory facade — the ``MemoryStore`` implementation for the foundation.

Combines an ``EmbeddingProvider`` with a ``VectorStore``: chunk → embed → upsert on
write, and embed → search → aggregate-by-paper on retrieve.
"""

from __future__ import annotations

from researchos.core.interfaces import EmbeddingProvider, VectorStore
from researchos.core.state import ResearchState
from researchos.ingestion.chunking import chunk_paper


class SemanticMemory:
    def __init__(self, embedder: EmbeddingProvider, vector_store: VectorStore) -> None:
        self._embedder = embedder
        self._store = vector_store

    def write_papers(self, state: ResearchState) -> int:
        """Embed and persist all papers in the working state. Returns chunk count."""
        chunks = [c for paper in state.papers.values() for c in chunk_paper(paper)]
        if not chunks:
            return 0
        vectors = self._embedder.embed([c.text for c in chunks])
        self._store.upsert(chunks, vectors, state.project_id)
        return len(chunks)

    def retrieve(self, query: str, k: int, project_id: str) -> list[tuple[str, float]]:
        """Return (paper_id, score) best-first, aggregating chunk hits by paper."""
        vector = self._embedder.embed([query])[0]
        hits = self._store.search(vector, k=k * 3, project_id=project_id)
        best: dict[str, float] = {}
        for chunk, score in hits:
            best[chunk.paper_id] = max(best.get(chunk.paper_id, -1.0), score)
        ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:k]
