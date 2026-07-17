"""Literature Agent — search and relevance ranking.

Owns interaction with source tools (arXiv today; Semantic Scholar / OpenAlex / GitHub
next) and relevance ranking against the research goal via semantic memory.
"""

from __future__ import annotations

from researchos.agents.base import BaseAgent
from researchos.core.models import Paper
from researchos.core.state import AgentResult, ResearchState, StateDelta, Task, TaskKind
from researchos.memory.store import SemanticMemory
from researchos.tools.base import BaseTool


class LiteratureAgent(BaseAgent):
    role = "literature"

    def __init__(self, search_tool: BaseTool, memory: SemanticMemory) -> None:
        self._tool = search_tool
        self._memory = memory

    def run(self, state: ResearchState, task: Task) -> AgentResult:
        if task.kind == TaskKind.SEARCH:
            return self._search(state, task)
        if task.kind == TaskKind.RANK:
            return self._rank(state, task)
        return self._result(ok=False, error=f"Literature agent cannot handle {task.kind}")

    def _search(self, state: ResearchState, task: Task) -> AgentResult:
        query = task.payload.get("query") or state.goal
        limit = int(task.payload.get("limit", 20))
        result = self._tool.invoke(query=query, limit=limit)
        if not result.ok:
            return self._result(ok=False, error=result.error, tool_calls=[self._tool.name])

        papers = [Paper(**d).ensure_id() for d in (result.data or [])]
        return self._result(
            output=f"Found {len(papers)} papers via {self._tool.name}.",
            delta=StateDelta(add_papers=papers),
            reasoning=[
                f"Searched {self._tool.name} for: {query!r} (limit {limit}).",
                f"Retrieved {len(papers)} candidate papers.",
            ],
            tool_calls=[self._tool.name],
        )

    def _rank(self, state: ResearchState, task: Task) -> AgentResult:
        if not state.papers:
            return self._result(output="No papers to rank.")
        hits = self._memory.retrieve(state.goal, k=len(state.papers), project_id=state.project_id)
        ranking = [pid for pid, _ in hits if pid in state.papers]
        # Fallback: any paper not surfaced by retrieval goes last, newest first.
        missing = [p.id for p in state.papers.values() if p.id not in ranking]
        missing.sort(key=lambda pid: state.papers[pid].year or 0, reverse=True)
        ranking.extend(missing)
        return self._result(
            output=f"Ranked {len(ranking)} papers by relevance to the goal.",
            delta=StateDelta(set_ranking=ranking),
            reasoning=[
                "Ranked papers by semantic relevance to the research goal using vector memory.",
                f"Top result: {state.papers[ranking[0]].title!r}" if ranking else "No ranking.",
            ],
        )
