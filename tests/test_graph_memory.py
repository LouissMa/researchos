"""Structural (knowledge-graph) memory tier: build, provenance rules, graph retrieval."""

import pytest

from researchos.core.models import GraphEdge
from researchos.memory.graph import SqliteGraphStore


def test_run_builds_knowledge_graph(orch):
    state = orch.start_run("graphtest", "knowledge graphs for llm reasoning", limit=6, top_cards=2)
    store = SqliteGraphStore()
    stats = store.stats("graphtest")

    assert stats["nodes"] >= len(state.papers)  # paper nodes
    assert "paper" in stats["by_type"]
    assert "concept" in stats["by_type"]  # cluster concepts merged in phase 2
    assert stats["edges"] > 0

    # Anti-hallucination: every persisted edge carries provenance + sane confidence.
    for edge in store.edges("graphtest", limit=500):
        assert any(k in edge.provenance for k in ("source_paper", "span", "tool"))
        assert 0.0 <= edge.confidence <= 1.0


def test_graph_retrieval_returns_connected_papers(orch):
    orch.start_run("graphretr", "long-term memory for llm agents", limit=6, top_cards=1)
    store = SqliteGraphStore()

    hits = store.search("memory agents", k=6, project_id="graphretr")
    assert hits  # keyword seed + BELONGS_TO expansion reaches papers
    paper_ids = [pid for pid, _ in hits]
    assert all(len(pid) == 16 for pid in paper_ids)  # paper ref ids, not node ids


def test_ungrounded_edge_is_rejected(settings):
    store = SqliteGraphStore()
    with pytest.raises(ValueError, match="[Uu]ngrounded"):
        store.upsert_edges(
            [
                GraphEdge(
                    relation="RELATED_TO",
                    source_id="a",
                    target_id="b",
                    provenance={},  # missing source_paper / span / tool
                )
            ],
            "p",
        )


def test_unknown_relation_is_rejected(settings):
    store = SqliteGraphStore()
    with pytest.raises(ValueError, match="[Uu]nknown graph relation"):
        store.upsert_edges(
            [
                GraphEdge(
                    relation="HYPOTHESIZES",
                    source_id="a",
                    target_id="b",
                    provenance={"tool": "test"},
                )
            ],
            "p",
        )


def test_graph_retrieval_is_deterministic_across_runs(orch):
    a = orch.start_run("graphdet", "episodic memory for autonomous agents", limit=6, top_cards=1)
    b = orch.start_run("graphdet", "episodic memory for autonomous agents", limit=6, top_cards=1)
    store = SqliteGraphStore()
    assert a.ranking == b.ranking
    assert store.search("episodic memory", k=6, project_id="graphdet") == store.search(
        "episodic memory", k=6, project_id="graphdet"
    )
