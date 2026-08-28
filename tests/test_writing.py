"""Writing agent: KG-grounded LaTeX draft + citation consistency (Phase 5)."""

from researchos.agents.writing import WritingAgent
from researchos.core.models import Draft
from researchos.llm.client import get_llm


def test_draft_grounded_in_project(orch):
    orch.start_run("writetest", "knowledge graphs for agent reasoning", limit=6, top_cards=2)
    draft = WritingAgent(get_llm(orch.settings)).draft("writetest")

    assert draft.sections  # Introduction / Related Work / ...
    assert draft.citations  # cites papers from the project
    assert len(draft.citations) >= 3
    assert "\\begin{document}" in draft.tex
    assert "\\begin{thebibliography}" in draft.tex

    # Related work comes from the knowledge graph's concept nodes (themes).
    assert any("Related Work" in s for s in draft.sections)

    # Consistency: every citation resolves to a bibitem, every bibitem is cited.
    assert draft.inconsistencies == []
    assert draft.generated_by == "heuristic"


def test_check_flags_dangling_citations():
    bad = Draft(
        id="d1",
        project_id="p",
        run_id="",
        tex=(
            "\\section{Related Work}\n"
            "\\citet{missing-key} is discussed here.\n"
            "\\begin{thebibliography}{99}\n"
            "\\bibitem{real-key} A Real Paper, 2024.\n"
            "\\end{thebibliography}"
        ),
        citations=["missing-key"],
    )
    issues = WritingAgent.check(bad)
    assert any("missing-key" in i for i in issues)  # dangling cite flagged
    assert any("real-key" in i for i in issues)  # uncited bibitem flagged


def test_draft_is_deterministic(orch):
    orch.start_run("writedet", "vector memory for agents", limit=6, top_cards=1)
    agent = WritingAgent(get_llm(orch.settings))
    a = agent.draft("writedet")
    b = agent.draft("writedet")
    assert a.tex == b.tex
    assert a.citations == b.citations
