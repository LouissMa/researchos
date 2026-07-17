"""End-to-end run of the orchestrator, fully offline (fake arXiv tool, local embeddings)."""

from researchos.persistence.event_log import EventLog


def test_full_literature_run(orch):
    state = orch.start_run("test", "long-term memory for LLM agents", limit=6, top_cards=3)

    # Papers discovered and ranked.
    assert len(state.papers) == 6
    assert len(state.ranking) == 6
    assert set(state.ranking) == set(state.papers)

    # Organized into themes and cards produced for the key papers.
    assert len(state.clusters) >= 1
    assert len(state.cards) == 3

    # Landscape assembled with a reading order covering every paper.
    assert state.landscape is not None
    assert len(state.landscape.reading_order) == 6
    assert state.landscape.key_papers  # non-empty

    # Critic reviewed the landscape.
    assert state.review is not None
    assert 0.0 <= state.review.score <= 10.0
    assert not state.reflected  # no gaps flagged by the (empty) coverage tool

    # The run is fully traced in the append-only event log.
    events = EventLog().list(state.run_id)
    types = {e.type for e in events}
    assert "run_started" in types
    assert "run_finished" in types
    assert "plan_created" in types


def test_run_is_reproducible_ranking(orch):
    a = orch.start_run("test", "vector memory for agents", limit=6, top_cards=2)
    b = orch.start_run("test", "vector memory for agents", limit=6, top_cards=2)
    # Deterministic embeddings ⇒ identical ranking across runs.
    assert a.ranking == b.ranking
