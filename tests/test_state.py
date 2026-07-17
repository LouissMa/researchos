from researchos.core.models import Paper
from researchos.core.state import ResearchState, StateDelta


def _state() -> ResearchState:
    return ResearchState(project_id="p", run_id="r", goal="g")


def test_paper_ensure_id_is_stable():
    a = Paper(source="arxiv", source_id="1", title="T").ensure_id()
    b = Paper(source="arxiv", source_id="1", title="T").ensure_id()
    assert a.id == b.id and a.id


def test_apply_delta_adds_and_ranks_papers():
    state = _state()
    paper = Paper(source="arxiv", source_id="1", title="T", abstract="A")
    state.apply(StateDelta(add_papers=[paper]))
    assert len(state.papers) == 1
    pid = next(iter(state.papers))
    assert state.papers[pid].id == pid  # id filled on apply

    state.apply(StateDelta(set_ranking=[pid]))
    assert state.ranked_papers()[0].id == pid


def test_delta_is_empty():
    assert StateDelta().is_empty()
    assert not StateDelta(add_notes=["x"]).is_empty()


def test_scratch_merges():
    state = _state()
    state.apply(StateDelta(scratch={"a": 1}))
    state.apply(StateDelta(scratch={"b": 2}))
    assert state.scratch == {"a": 1, "b": 2}
