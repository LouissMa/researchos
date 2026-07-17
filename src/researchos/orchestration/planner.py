"""Planner — task decomposition.

The foundation ships a deterministic plan for the literature-discovery workflow. This is
the seam where an LLM-driven or graph-based planner (LangGraph) will slot in: same
output (an ordered list of ``Task``), richer decision-making.
"""

from __future__ import annotations

from researchos.core.state import Task, TaskKind


class Planner:
    role = "planner"

    def plan(self, goal: str, *, limit: int = 20, top_cards: int = 5) -> list[Task]:
        return [
            Task(
                id="t1",
                kind=TaskKind.SEARCH,
                description="Search sources for the goal",
                payload={"limit": limit},
            ),
            Task(id="t2", kind=TaskKind.INGEST, description="Embed & index papers in memory"),
            Task(id="t3", kind=TaskKind.RANK, description="Rank papers by relevance"),
            Task(id="t4", kind=TaskKind.CLUSTER, description="Organize papers into themes"),
            Task(
                id="t5",
                kind=TaskKind.CARD,
                description="Deep-read the key papers",
                payload={"top_n": top_cards},
            ),
            Task(id="t6", kind=TaskKind.LANDSCAPE, description="Assemble the research landscape"),
        ]
