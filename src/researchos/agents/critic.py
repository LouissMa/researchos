"""Critic Agent — critical review of the research landscape.

Implements the Planner–Worker–Critic pattern (ARCHITECTURE §3). For the literature
workflow it performs a **citation-coverage check** (are we missing highly-cited seminal
work?), assesses thematic balance, and produces a scored :class:`Review`. The missing
papers it surfaces feed the orchestrator's bounded reflection loop.
"""

from __future__ import annotations

import re

from researchos.agents.base import BaseAgent
from researchos.core.interfaces import LLM
from researchos.core.models import Paper, Review
from researchos.core.state import AgentResult, ResearchState, StateDelta, Task, TaskKind
from researchos.tools.base import BaseTool

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_SEMINAL_MIN_CITATIONS = 50


def _norm(title: str) -> str:
    return _NON_ALNUM.sub("", title.lower())


class CriticAgent(BaseAgent):
    role = "critic"

    def __init__(self, llm: LLM, coverage_tool: BaseTool | None = None) -> None:
        self._llm = llm
        self._coverage_tool = coverage_tool

    def run(self, state: ResearchState, task: Task) -> AgentResult:
        if task.kind == TaskKind.REVIEW:
            return self._review(state)
        return self._result(ok=False, error=f"Critic cannot handle {task.kind}")

    def _review(self, state: ResearchState) -> AgentResult:
        missing, coverage = self._coverage_check(state)
        balance, imbalanced = self._cluster_balance(state)

        strengths: list[str] = []
        weaknesses: list[str] = []
        suggestions: list[str] = []

        if state.clusters:
            strengths.append(
                f"Organized {len(state.papers)} papers into {len(state.clusters)} themes."
            )
        years = [p.year for p in state.papers.values() if p.year]
        if years:
            strengths.append(f"Spans {min(years)}–{max(years)}.")

        if missing:
            weaknesses.append(f"{len(missing)} highly-cited papers appear to be missing.")
            suggestions.append("Incorporate the flagged seminal papers (see missing_seminal).")
        if imbalanced:
            weaknesses.append("Themes are imbalanced; one cluster dominates.")
            suggestions.append("Broaden queries to balance under-represented themes.")
        if not missing and not imbalanced:
            strengths.append("Good citation coverage and balanced themes.")

        score = 8.0
        score -= min(3.0, 0.6 * len(missing))
        score -= 1.5 if imbalanced else 0.0
        score -= 1.0 if len(state.papers) < 5 else 0.0
        score = round(max(0.0, min(10.0, score)), 1)

        review = Review(
            coverage=coverage,
            cluster_balance=balance,
            missing_seminal=[p.title for p in missing[:5]],
            strengths=strengths,
            weaknesses=weaknesses,
            suggestions=suggestions,
            score=score,
            reviewed_by=self._llm.name if self._llm.available else "critic",
        )
        return self._result(
            output=f"Reviewed landscape — score {score}/10, {len(missing)} gaps flagged.",
            delta=StateDelta(
                set_review=review,
                scratch={"missing_papers": [p.model_dump() for p in missing[:5]]},
            ),
            reasoning=[coverage, balance] + [f"Suggestion: {s}" for s in suggestions],
            tool_calls=[self._coverage_tool.name] if self._coverage_tool else [],
        )

    def _coverage_check(self, state: ResearchState) -> tuple[list[Paper], str]:
        if self._coverage_tool is None:
            return [], "Coverage check skipped (no citation source configured)."
        result = self._coverage_tool.invoke(query=state.goal, limit=20, sort="cited_by_count:desc")
        if not result.ok:
            return [], f"Coverage check unavailable: {result.error}"
        candidates = [Paper(**d) for d in (result.data or [])]
        have = {_norm(p.title) for p in state.papers.values()}
        have |= {p.doi.lower() for p in state.papers.values() if p.doi}
        missing = [
            c
            for c in candidates
            if (c.citation_count or 0) >= _SEMINAL_MIN_CITATIONS
            and _norm(c.title) not in have
            and (not c.doi or c.doi.lower() not in have)
        ]
        note = (
            f"Checked the {len(candidates)} most-cited works for the topic; "
            f"{len(missing)} high-impact papers (≥{_SEMINAL_MIN_CITATIONS} citations) "
            f"are missing from the set."
        )
        return missing, note

    @staticmethod
    def _cluster_balance(state: ResearchState) -> tuple[str, bool]:
        sizes = [len(c.paper_ids) for c in state.clusters]
        if not sizes:
            return "No clusters to assess.", False
        total = sum(sizes) or 1
        largest = max(sizes)
        imbalanced = largest / total > 0.7 and len(sizes) > 1
        note = (
            f"Theme sizes: {sizes}. Largest holds {largest}/{total} papers"
            f"{' — imbalanced.' if imbalanced else '.'}"
        )
        return note, imbalanced
