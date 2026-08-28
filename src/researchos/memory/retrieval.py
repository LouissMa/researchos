"""Retrieval strategies — the swappable, benchmarkable retrieval policies (ADR-0002).

Three strategies implement the :class:`~researchos.core.interfaces.RetrievalStrategy`
seam, each a genuinely different signal:

- **vector** — embedding search over the semantic tier (Qdrant chunks).
- **graph** — structural traversal over the knowledge-graph tier (keyword seed → edges).
- **hybrid** — reciprocal-rank fusion (RRF) of vector + graph ranks.

The factory degrades gracefully: without a graph store, ``graph``/``hybrid`` fall back to
``vector`` so the system never breaks offline. Benchmarks (``benchmarks/run_eval.py``)
compare the strategies head-to-head on frozen scenarios.
"""

from __future__ import annotations

from collections.abc import Callable

from researchos.core.interfaces import GraphStore, RetrievalStrategy

RetrieveFn = Callable[[str, int, str], list[tuple[str, float]]]


class VectorRetrieval:
    """Semantic retrieval over the vector tier (embeddings)."""

    name = "vector"

    def __init__(self, vector_fn: RetrieveFn) -> None:
        self._vector = vector_fn

    def retrieve(self, query: str, k: int, project_id: str) -> list[tuple[str, float]]:
        return self._vector(query, k, project_id)


class GraphRetrieval:
    """Structural retrieval over the knowledge-graph tier (traversal)."""

    name = "graph"

    def __init__(self, graph: GraphStore) -> None:
        self._graph = graph

    def retrieve(self, query: str, k: int, project_id: str) -> list[tuple[str, float]]:
        return self._graph.search(query, k, project_id)


def _rrf(rankings: list[list[tuple[str, float]]], fusion_k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion — deterministic, parameter-light rank merging."""
    scores: dict[str, float] = {}
    for ranked in rankings:
        for rank, (pid, _score) in enumerate(ranked):
            scores[pid] = scores.get(pid, 0.0) + 1.0 / (fusion_k + rank + 1)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


class HybridRetrieval:
    """Fuses vector + graph ranks with RRF; robust to either side returning nothing."""

    name = "hybrid"

    def __init__(
        self, vector: RetrievalStrategy, graph: RetrievalStrategy, *, fusion_k: int = 60
    ) -> None:
        self._vector = vector
        self._graph = graph
        self._fusion_k = fusion_k

    def retrieve(self, query: str, k: int, project_id: str) -> list[tuple[str, float]]:
        merged = _rrf(
            [
                self._vector.retrieve(query, k, project_id),
                self._graph.retrieve(query, k, project_id),
            ],
            fusion_k=self._fusion_k,
        )
        return merged[:k]


def get_retrieval_strategy(
    name: str, *, vector_fn: RetrieveFn, graph: GraphStore | None
) -> RetrievalStrategy:
    """Factory. ``vector | graph | hybrid``; degrades to vector when no graph store exists."""
    vector = VectorRetrieval(vector_fn)
    if name == "vector" or graph is None:
        return vector
    graph_strategy = GraphRetrieval(graph)
    if name == "graph":
        return graph_strategy
    if name == "hybrid":
        return HybridRetrieval(vector, graph_strategy)
    raise ValueError(f"Unknown retrieval strategy: {name!r} (vector | graph | hybrid)")
