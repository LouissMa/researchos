"""Critic agent: citation-coverage review and the bounded reflection loop."""

from researchos.agents.critic import CriticAgent
from researchos.core.models import Paper
from researchos.core.state import ResearchState, StateDelta, Task, TaskKind
from tests.conftest import FakeCoverageTool, FakeMissingCoverageTool


def _state_with_papers() -> ResearchState:
    st = ResearchState(project_id="p", run_id="r", goal="agent memory")
    st.apply(StateDelta(add_papers=[Paper(source="arxiv", source_id="1", title="Known Paper")]))
    st.apply(StateDelta(set_ranking=list(st.papers)))
    return st


def test_critic_flags_missing_seminal_paper():
    critic = CriticAgent(llm=_NullLLM(), coverage_tool=FakeMissingCoverageTool())
    result = critic.run(_state_with_papers(), Task(id="rv", kind=TaskKind.REVIEW))
    review = result.delta.set_review
    assert review is not None
    assert review.missing_seminal  # the seminal paper was flagged
    assert result.delta.scratch["missing_papers"]  # surfaced for reflection


def test_critic_clean_when_no_gaps():
    critic = CriticAgent(llm=_NullLLM(), coverage_tool=FakeCoverageTool())
    result = critic.run(_state_with_papers(), Task(id="rv", kind=TaskKind.REVIEW))
    review = result.delta.set_review
    assert review is not None
    assert not review.missing_seminal
    assert review.score >= 6.0


def test_reflection_adds_missing_papers(orch):
    orch.critic._coverage_tool = FakeMissingCoverageTool()
    try:
        state = orch.start_run("reflect", "long-term memory for agents", limit=6, top_cards=2)
        assert state.reflected is True
        assert state.review.missing_seminal
        assert len(state.papers) == 7  # 6 discovered + 1 injected via reflection
    finally:
        orch.critic._coverage_tool = FakeCoverageTool()


class _NullLLM:
    name = "null"
    available = False

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        return ""
