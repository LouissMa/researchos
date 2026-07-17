"""Qdrant-backed vector store.

Runs **embedded** by default (local on-disk, no server) so the foundation needs no extra
infrastructure. Point payloads carry ``project_id`` for hard project isolation and
filtered search.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from researchos.core.models import PaperChunk

_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-0000000005ea")


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, chunk_id))


class QdrantVectorStore:
    def __init__(
        self,
        dim: int,
        *,
        mode: str = "embedded",
        path: Path | None = None,
        url: str | None = None,
        collection: str = "chunks",
    ) -> None:
        if mode == "server":
            self.client = QdrantClient(url=url)
        else:
            self.client = QdrantClient(path=str(path or "./data/qdrant"))
        self.dim = dim
        self.collection = collection
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        existing = {c.name for c in self.client.get_collections().collections}
        if self.collection not in existing:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE),
            )

    def upsert(self, chunks: list[PaperChunk], vectors: list[list[float]], project_id: str) -> None:
        points = [
            PointStruct(
                id=_point_id(chunk.id),
                vector=vec,
                payload={
                    "chunk_id": chunk.id,
                    "paper_id": chunk.paper_id,
                    "section": chunk.section,
                    "index": chunk.index,
                    "text": chunk.text,
                    "project_id": project_id,
                },
            )
            for chunk, vec in zip(chunks, vectors, strict=False)
        ]
        if points:
            self.client.upsert(collection_name=self.collection, points=points)

    def search(
        self, vector: list[float], k: int, project_id: str
    ) -> list[tuple[PaperChunk, float]]:
        response = self.client.query_points(
            collection_name=self.collection,
            query=vector,
            limit=k,
            with_payload=True,
            query_filter=Filter(
                must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))]
            ),
        )
        results: list[tuple[PaperChunk, float]] = []
        for hit in response.points:
            p = hit.payload or {}
            chunk = PaperChunk(
                id=p.get("chunk_id", ""),
                paper_id=p.get("paper_id", ""),
                section=p.get("section", "abstract"),
                index=int(p.get("index", 0)),
                text=p.get("text", ""),
            )
            results.append((chunk, float(hit.score)))
        return results
