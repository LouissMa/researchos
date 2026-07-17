"""The seams of the system.

Every subsystem is defined here as a ``Protocol`` (structural interface). Concrete
implementations live in their own modules and can be swapped without touching callers.
This is what makes ResearchOS modular by construction (ARCHITECTURE.md §1, principle 3).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from researchos.core.models import PaperChunk
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
    semantic (vector) retrieval; reflection/consolidation/decay arrive in Phase 2."""

    def write_papers(self, state: ResearchState) -> int: ...

    def retrieve(self, query: str, k: int, project_id: str) -> list[tuple[str, float]]: ...


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
