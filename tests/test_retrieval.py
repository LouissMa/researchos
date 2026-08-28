"""Retrieval strategies: selection, fusion, and semantic-memory dispatch."""

import pytest

from researchos.memory.graph import SqliteGraphStore
from researchos.memory.retrieval import (
    GraphRetrieval,
    HybridRetrieval,
    VectorRetrieval,
    get_retrieval_strategy,
)


def _vector_fn(query: str, k: int, project_id: str):
    return [("p1", 0.9), ("p2", 0.7), ("p3", 0.5)][:k]


def test_factory_selects_each_strategy():
    graph = SqliteGraphStore()
    for name, expected in (
        ("vector", VectorRetrieval),
        ("graph", GraphRetrieval),
        ("hybrid", HybridRetrieval),
    ):
        strategy = get_retrieval_strategy(name, vector_fn=_vector_fn, graph=graph)
        assert isinstance(strategy, expected)
        assert strategy.name == name


def test_factory_degrades_without_graph_store():
    strategy = get_retrieval_strategy("hybrid", vector_fn=_vector_fn, graph=None)
    assert isinstance(strategy, VectorRetrieval)  # never breaks offline
    assert strategy.retrieve("q", 2, "p") == [("p1", 0.9), ("p2", 0.7)]


def test_factory_rejects_unknown_strategy():
    graph = SqliteGraphStore()
    with pytest.raises(ValueError, match="[Uu]nknown retrieval strategy"):
        get_retrieval_strategy("banana", vector_fn=_vector_fn, graph=graph)


def test_hybrid_fuses_ranks():
    vector = VectorRetrieval(lambda q, k, pid: [("p1", 1.0), ("p3", 0.8), ("p4", 0.6)])
    graph = GraphRetrieval(_FakeGraph())
    hybrid = HybridRetrieval(vector, graph)
    fused = hybrid.retrieve("q", 5, "p")
    ids = [pid for pid, _ in fused]
    assert "p2" in ids  # graph-only hit surfaces via fusion
    assert ids[0] == "p1"  # top of both lists stays top


class _FakeGraph:
    def search(self, query: str, k: int, project_id: str):
        return [("p2", 1.0), ("p1", 0.9), ("p5", 0.4)]


def test_semantic_memory_dispatches_through_strategy(orch):
    orch.start_run("retrtest", "vector memory for llm agents", limit=6, top_cards=2)
    hits = orch.memory.retrieve("vector memory", k=5, project_id="retrtest")
    assert hits
    assert orch.memory.strategy.name == orch.settings.retrieval_strategy == "hybrid"
    # Deterministic across repeated queries.
    assert hits == orch.memory.retrieve("vector memory", k=5, project_id="retrtest")
