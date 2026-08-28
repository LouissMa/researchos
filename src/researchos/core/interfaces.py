"""The seams of the system.

Every subsystem is defined here as a ``Protocol`` (structural interface). Concrete
implementations live in their own modules and can be swapped without touching callers.
This is what makes ResearchOS modular by construction (ARCHITECTURE.md §1, principle 3).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from researchos.core.models import GraphEdge, GraphNode, PaperChunk
from researchos.core.state import AgentResult, ResearchState, Task


# --------------------------------------------------------------------------- Tools
class ToolResult(BaseModel):
    ok: bool = True
    data: Any = None
    error: str | None = None
    cost: float = 0.0


@runtime_checkable
class Tool(Protocol):
    """An MCP-style tool. Read tools are free/cacheable; side-effecting tools need auth."""

    name: str
    description: str
    side_effects: bool

    def input_schema(self) -> dict[str, Any]: ...

    def invoke(self, **kwargs: Any) -> ToolResult: ...


# ---------------------------------------------------------------------- Embeddings
@runtime_checkable
class EmbeddingProvider(Protocol):
    """Turns text into vectors. ``local`` default needs no downloads or network."""

    name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


# ---------------------------------------------------------------------------- LLM
@runtime_checkable
class LLM(Protocol):
    """A minimal chat/completion interface over any OpenAI-compatible backend.

    ``available`` is False for the null provider, letting callers degrade gracefully to
    heuristics instead of failing when no key is configured.
    """

    name: str
    available: bool

    def complete(self, prompt: str, *, system: str | None = None) -> str: ...


# ------------------------------------------------------------------- Vector store
@runtime_checkable
class VectorStore(Protocol):
    def upsert(
        self, chunks: list[PaperChunk], vectors: list[list[float]], project_id: str
    ) -> None: ...

    def search(
        self, vector: list[float], k: int, project_id: str
    ) -> list[tuple[PaperChunk, float]]: ...


# -------------------------------------------------------------------- Memory store
@runtime_checkable
class MemoryStore(Protocol):
    """Facade over the tiered memory (ARCHITECTURE.md §4). The foundation implements
    semantic (vector) retrieval; reflection/consolidation/decay and the structural
    (graph) tier arrive in Phase 2 behind the same interface."""

    def write_papers(self, state: ResearchState) -> int: ...

    def retrieve(self, query: str, k: int, project_id: str) -> list[tuple[str, float]]: ...


# ------------------------------------------------------------ Retrieval strategies
@runtime_checkable
class RetrievalStrategy(Protocol):
    """A swappable retrieval policy over the memory tiers (ADR-0002).

    Returns ``(paper_id, score)`` best-first. Concrete variants — ``vector``
    (embeddings), ``graph`` (structural traversal), ``hybrid`` (fusion) — live in
    ``researchos.memory.retrieval`` and can be benchmarked against each other.
    """

    name: str

    def retrieve(self, query: str, k: int, project_id: str) -> list[tuple[str, float]]: ...


# -------------------------------------------------------------------- Graph store
@runtime_checkable
class GraphStore(Protocol):
    """The structural memory tier: a knowledge graph of typed, provenance-carrying
    edges (ADR-0003). SQLite/Postgres first; Neo4j is a drop-in implementation."""

    def upsert_nodes(self, nodes: list[GraphNode], project_id: str) -> int: ...

    def upsert_edges(self, edges: list[GraphEdge], project_id: str) -> int: ...

    def clear(self, project_id: str) -> None: ...

    def search(self, query: str, k: int, project_id: str) -> list[tuple[str, float]]: ...

    def stats(self, project_id: str) -> dict: ...


# -------------------------------------------------------------------------- Agents
@runtime_checkable
class Agent(Protocol):
    role: str

    def run(self, state: ResearchState, task: Task) -> AgentResult: ...


# -------------------------------------------------------------------- Orchestrator
@runtime_checkable
class Orchestrator(Protocol):
    """Drives a run over ``ResearchState``. LangGraph is one implementation; the
    foundation ships a dependency-free sequential one (ADR-0001)."""

    def start_run(self, project_id: str, goal: str, **kwargs: Any) -> ResearchState: ...

    def stream(self) -> Iterator[Any]: ...
