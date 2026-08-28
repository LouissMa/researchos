"""Shared run state and the delta protocol.

Central rule (see ARCHITECTURE.md §3): **agents never mutate ``ResearchState`` directly.**
They return a :class:`StateDelta`; the orchestrator applies it. Every change is therefore
typed, diffable, and replayable.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from researchos.core.models import (
    Cluster,
    Landscape,
    Paper,
    ResearchCard,
    ResearchIdea,
    Review,
)


class TaskKind(StrEnum):
    SEARCH = "search"
    INGEST = "ingest"
    RANK = "rank"
    CLUSTER = "cluster"
    CARD = "card"
    CODE = "code"
    LANDSCAPE = "landscape"
    REVIEW = "review"
    IDEA = "idea"


class Task(BaseModel):
    """A unit of work the planner routes to an agent."""

    id: str
    kind: TaskKind
    description: str = ""
    payload: dict = Field(default_factory=dict)


class StateDelta(BaseModel):
    """A typed patch produced by an agent and applied by the runtime."""

    add_papers: list[Paper] = Field(default_factory=list)
    set_ranking: list[str] | None = None
    add_clusters: list[Cluster] = Field(default_factory=list)
    add_cards: list[ResearchCard] = Field(default_factory=list)
    add_ideas: list[ResearchIdea] = Field(default_factory=list)
    set_landscape: Landscape | None = None
    set_review: Review | None = None
    add_notes: list[str] = Field(default_factory=list)
    scratch: dict = Field(default_factory=dict)

    def is_empty(self) -> bool:
        return (
            not self.add_papers
            and self.set_ranking is None
            and not self.add_clusters
            and not self.add_cards
            and not self.add_ideas
            and self.set_landscape is None
            and self.set_review is None
            and not self.add_notes
            and not self.scratch
        )


class ResearchState(BaseModel):
    """The working set for a single run. Not the source of truth for durable memory."""

    project_id: str
    run_id: str
    goal: str

    papers: dict[str, Paper] = Field(default_factory=dict)
    ranking: list[str] = Field(default_factory=list)  # paper ids, best first
    clusters: list[Cluster] = Field(default_factory=list)
    cards: dict[str, ResearchCard] = Field(default_factory=dict)  # by paper_id
    ideas: list[ResearchIdea] = Field(default_factory=list)
    landscape: Landscape | None = None
    review: Review | None = None
    notes: list[str] = Field(default_factory=list)
    scratch: dict = Field(default_factory=dict)

    # Loop / budget control (enforced by the planner).
    step: int = 0
    max_steps: int = 16
    reflected: bool = False  # guards the single bounded reflection iteration

    def apply(self, delta: StateDelta) -> ResearchState:
        """Apply a delta in place, using explicit per-field reducers."""
        for paper in delta.add_papers:
            paper.ensure_id()
            self.papers[paper.id] = paper
        if delta.set_ranking is not None:
            self.ranking = delta.set_ranking
        if delta.add_clusters:
            self.clusters.extend(delta.add_clusters)
        for card in delta.add_cards:
            self.cards[card.paper_id] = card
        if delta.add_ideas:
            self.ideas.extend(delta.add_ideas)
        if delta.set_landscape is not None:
            self.landscape = delta.set_landscape
        if delta.set_review is not None:
            self.review = delta.set_review
        if delta.add_notes:
            self.notes.extend(delta.add_notes)
        if delta.scratch:
            self.scratch.update(delta.scratch)
        return self

    def ranked_papers(self) -> list[Paper]:
        """Papers in ranked order (falls back to insertion order)."""
        if self.ranking:
            return [self.papers[pid] for pid in self.ranking if pid in self.papers]
        return list(self.papers.values())


class AgentResult(BaseModel):
    """What every agent returns. Observable and mergeable."""

    agent: str
    output: str = ""
    delta: StateDelta = Field(default_factory=StateDelta)
    reasoning: list[str] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
    cost: float = 0.0
    ok: bool = True
    error: str | None = None
