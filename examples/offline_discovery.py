"""Fully offline end-to-end example: literature discovery with zero network or keys.

    python examples/offline_discovery.py

Works on any machine with ResearchOS installed (no arXiv, no API keys, no model
downloads): a built-in fake source stands in for the real search tools, embeddings are
the deterministic local provider, and Qdrant runs embedded. Prints the full run: ranking,
themes, critic score, and the Idea agent's research proposals.

Swap in the real pipeline by using `uv run researchos discover "<goal>"` (real arXiv +
OpenAlex) or the CLI/server entry points.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from researchos.config import Settings
from researchos.core.interfaces import ToolResult
from researchos.observability.events import Event
from researchos.orchestration.orchestrator import SequentialOrchestrator
from researchos.tools.base import BaseTool

_FAKE_PAPERS = [
    {
        "source": "arxiv",
        "source_id": "2401.00001",
        "title": "Long-Term Memory Architectures for LLM Agents",
        "abstract": "We study long-term memory mechanisms enabling language model agents to "
        "retain and retrieve knowledge across sessions using vector memory.",
        "authors": ["A. One"],
        "url": "http://arxiv.org/abs/2401.00001",
    },
    {
        "source": "arxiv",
        "source_id": "2401.00002",
        "title": "Retrieval-Augmented Generation: A Survey",
        "abstract": "A survey of retrieval-augmented generation methods combining dense "
        "retrieval with generative language models for knowledge-intensive tasks.",
        "authors": ["B. Two"],
        "url": "http://arxiv.org/abs/2401.00002",
    },
    {
        "source": "arxiv",
        "source_id": "2401.00003",
        "title": "Knowledge Graphs for Agent Reasoning",
        "abstract": "We connect knowledge graphs to language model agents to improve "
        "multi-hop reasoning and structured memory retrieval.",
        "authors": ["C. Three"],
        "url": "http://arxiv.org/abs/2401.00003",
    },
    {
        "source": "arxiv",
        "source_id": "2401.00004",
        "title": "Salience-Based Forgetting in Agent Memory Systems",
        "abstract": "We propose salience decay policies that let agent memory systems forget "
        "low-value items while preserving pinned knowledge across long horizons.",
        "authors": ["D. Four"],
        "url": "http://arxiv.org/abs/2401.00004",
    },
]


class OfflineArxivTool(BaseTool):
    """A fake source tool — the offline stand-in for the real arXiv/OpenAlex tools."""

    name = "arxiv_search"
    description = "Offline fake source for the fully-offline example."
    side_effects = False

    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"query": {"type": "string"}}}

    def invoke(self, **kwargs: Any) -> ToolResult:
        return ToolResult(ok=True, data=_FAKE_PAPERS)


class OfflineCoverageTool(BaseTool):
    """Offline coverage tool reporting no missing seminal work."""

    name = "openalex_search"
    description = "Offline fake coverage tool."
    side_effects = False

    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"query": {"type": "string"}}}

    def invoke(self, **kwargs: Any) -> ToolResult:
        return ToolResult(ok=True, data=[])


def main() -> None:
    goal = "long-term memory mechanisms for llm agents"
    # A dedicated temp data dir so the demo never touches ./data or collides with a
    # previously created Qdrant collection of a different dimension.
    data_dir = Path(tempfile.mkdtemp(prefix="researchos_example_"))
    settings = Settings(data_dir=data_dir, embedding_dim=64)  # smaller dim → fast

    def on_event(ev: Event) -> None:
        text = ev.payload.get("text") or ev.payload.get("output") or ""
        print(f"  [{ev.actor:>10}] {ev.type.value} {text}".rstrip())

    orch = SequentialOrchestrator(settings)
    orch.literature._tools = [OfflineArxivTool()]  # example: inject the fake source
    orch.knowledge._code_tool = None  # no GitHub network in this example
    orch.critic._coverage_tool = OfflineCoverageTool()  # no OpenAlex network

    state = orch.start_run("example", goal, limit=4, top_cards=2, on_event=on_event)

    print("\n=== LANDSCAPE ===")
    if state.landscape:
        print(state.landscape.summary, "\n")
        for i, pid in enumerate(state.landscape.reading_order, 1):
            paper = state.papers.get(pid)
            if paper:
                print(f"  {i}. {paper.title} ({paper.year or 'n.d.'})")
    print(f"\n=== CRITIC ===  score {state.review.score if state.review else 'n/a'}/10")
    if state.ideas:
        print("\n=== RESEARCH IDEAS (Idea agent) ===")
        for idea in state.ideas:
            print(f"  - {idea.title}")
    print(
        f"\nRun {state.run_id}: {len(state.papers)} papers · {len(state.clusters)} themes "
        f"· graph {orch.graph_store.stats('example')['edges']} edges"
    )

    shutil.rmtree(data_dir, ignore_errors=True)  # best-effort cleanup of the demo data


if __name__ == "__main__":
    main()
