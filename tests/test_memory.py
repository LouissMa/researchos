"""Tiered memory operations: consolidation, reflection, and forgetting (decay)."""

from researchos.memory.manager import MemoryManager


def test_consolidate_reflect_and_decay(orch):
    state = orch.start_run("memtest", "vector memory for llm agents", limit=6, top_cards=2)
    mm = MemoryManager()

    papers = mm.list_items("memtest", ref_type="paper")
    concepts = mm.list_items("memtest", ref_type="concept")
    interests = mm.list_items("memtest", ref_type="interest")

    assert len(papers) == len(state.papers) == 6
    assert len(concepts) >= 1  # clusters consolidated into concepts
    assert len(interests) == 1 and interests[0].pinned  # interest profile is pinned

    # Forgetting: decay reduces non-pinned salience, leaves pinned interest untouched.
    before = {i.ref_id: i.salience for i in papers}
    pinned_salience = interests[0].salience
    changed = mm.decay("memtest", rate=0.5)
    after = {i.ref_id: i.salience for i in mm.list_items("memtest", ref_type="paper")}

    assert changed >= 6
    assert all(after[k] < before[k] for k in before)
    assert mm.list_items("memtest", ref_type="interest")[0].salience == pinned_salience


def test_reflect_profile_reflects_goal_terms(orch):
    orch.start_run("reflecttest", "long-term episodic memory for agents", limit=6, top_cards=1)
    profile = MemoryManager().reflect("reflecttest")
    assert "memory" in profile.lower()
