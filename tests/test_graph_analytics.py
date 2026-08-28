"""Graph analytics: degree centrality + community detection (Phase 3)."""

from researchos.memory.graph import SqliteGraphStore


def test_centrality_ranks_connected_nodes(orch):
    orch.start_run("analyticstest", "knowledge graphs for agent reasoning", limit=6, top_cards=1)
    store = SqliteGraphStore()
    central = store.centrality("analyticstest")
    assert central
    for node_id, degree, norm in central:
        assert node_id
        assert degree > 0
        assert 0.0 <= norm <= 1.0
    # Top node is a paper or concept with the most connections.
    assert central[0][1] >= central[-1][1]


def test_components_find_communities(orch):
    orch.start_run("componentstest", "episodic memory for agents", limit=6, top_cards=1)
    store = SqliteGraphStore()
    comps = store.components("componentstest")
    # Co-cluster edges connect papers into at least one multi-node community.
    assert any(len(c) > 1 for c in comps)
    # Components are disjoint.
    seen: set[str] = set()
    for comp in comps:
        assert not (seen & set(comp))
        seen.update(comp)


def test_analytics_empty_project(orch):
    assert SqliteGraphStore().centrality("no-such-project") == []
    assert SqliteGraphStore().components("no-such-project") == []
