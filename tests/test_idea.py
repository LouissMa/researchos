"""Idea agent: grounded gap analysis over the landscape (Phase 3)."""

from researchos.persistence.store import Store


def test_idea_agent_proposes_grounded_ideas(orch):
    state = orch.start_run("ideatest", "long-term memory for llm agents", limit=6, top_cards=2)

    assert state.ideas  # heuristic gap analysis produced at least one proposal
    for idea in state.ideas:
        assert idea.title and idea.hypothesis
        assert idea.grounding  # every idea is grounded in cluster/paper ids
        assert 0.0 <= idea.novelty <= 1.0
        assert 0.0 <= idea.feasibility <= 1.0
        assert idea.generated_by == "heuristic"

    # Proposals are persisted (idempotent by id) and inspectable via the store.
    rows = Store().list_ideas("ideatest")
    assert len(rows) == len(state.ideas)
    assert {r.id for r in rows} == {i.id for i in state.ideas}


def test_idea_generation_is_deterministic(orch):
    a = orch.start_run("ideadet", "vector memory for agents", limit=6, top_cards=1)
    b = orch.start_run("ideadet", "vector memory for agents", limit=6, top_cards=1)
    assert [(i.title, i.novelty, i.grounding) for i in a.ideas] == [
        (i.title, i.novelty, i.grounding) for i in b.ideas
    ]
