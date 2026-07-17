"""Literature Agent — multi-source search, cross-source dedup, and relevance ranking.

Owns interaction with source tools (arXiv, Semantic Scholar, OpenAlex; GitHub next):
queries every configured source, merges duplicates into the richest record, and ranks
the result against the research goal via semantic memory.
"""

from __future__ import annotations

from researchos.agents.base import BaseAgent
from researchos.core.models import Paper
from researchos.core.state import AgentResult, ResearchState, StateDelta, Task, TaskKind
from researchos.ingestion.dedup import dedup_papers
from researchos.memory.store import SemanticMemory
from researchos.tools.base import BaseTool


class LiteratureAgent(BaseAgent):
    role = "literature"

    def __init__(self, search_tools: list[BaseTool], memory: SemanticMemory) -> None:
        if not search_tools:
            raise ValueError("LiteratureAgent needs at least one search tool.")
        self._tools = search_tools
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

        raw: list[Paper] = []
        reasoning: list[str] = []
        tool_calls: list[str] = []
        per_source: dict[str, int] = {}
        for tool in self._tools:
            tool_calls.append(tool.name)
            result = tool.invoke(query=query, limit=limit)
            if not result.ok:
                reasoning.append(f"{tool.name} failed: {result.error}")
                continue
            found = [Paper(**d).ensure_id() for d in (result.data or [])]
            per_source[tool.name] = len(found)
            raw.extend(found)
            reasoning.append(f"{tool.name}: {len(found)} papers for {query!r}.")

        if not raw:
            return self._result(
                ok=False,
                error="All configured sources returned no results or failed.",
                reasoning=reasoning,
                tool_calls=tool_calls,
            )

        deduped = dedup_papers(raw)
        removed = len(raw) - len(deduped)
        reasoning.append(
            f"Merged {len(raw)} results from {len(per_source)} sources → "
            f"{len(deduped)} unique papers ({removed} cross-source duplicates)."
        )
        return self._result(
            output=f"Found {len(deduped)} unique papers across {len(per_source)} sources.",
            delta=StateDelta(add_papers=deduped, scratch={"per_source": per_source}),
            reasoning=reasoning,
            tool_calls=tool_calls,
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
