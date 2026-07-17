"""Shared fixtures. All fixtures here are offline — no network, no API keys."""

from __future__ import annotations

from typing import Any

import pytest

from researchos.config import Settings
from researchos.core.interfaces import ToolResult
from researchos.tools.base import BaseTool

_FAKE_PAPERS = [
    {
        "source": "arxiv",
        "source_id": "2401.00001",
        "title": "Long-Term Memory Architectures for LLM Agents",
        "abstract": "We study long-term memory mechanisms enabling language model agents to "
        "retain and retrieve knowledge across sessions using vector memory.",
        "authors": ["A. One", "B. Two"],
        "url": "http://arxiv.org/abs/2401.00001",
    },
    {
        "source": "arxiv",
        "source_id": "2401.00002",
        "title": "Episodic Memory and Reflection in Autonomous Agents",
        "abstract": "A framework for episodic memory, reflection, and consolidation in "
        "autonomous agents built on large language models.",
        "authors": ["C. Three"],
        "url": "http://arxiv.org/abs/2401.00002",
    },
    {
        "source": "arxiv",
        "source_id": "2401.00003",
        "title": "Retrieval-Augmented Generation Survey",
        "abstract": "A survey of retrieval-augmented generation methods combining dense "
        "retrieval with generative language models for knowledge-intensive tasks.",
        "authors": ["D. Four"],
        "url": "http://arxiv.org/abs/2401.00003",
    },
    {
        "source": "arxiv",
        "source_id": "2401.00004",
        "title": "Knowledge Graphs for Agent Reasoning",
        "abstract": "We connect knowledge graphs to language model agents to improve "
        "multi-hop reasoning and structured memory retrieval.",
        "authors": ["E. Five"],
        "url": "http://arxiv.org/abs/2401.00004",
    },
    {
        "source": "arxiv",
        "source_id": "2401.00005",
        "title": "Vector Databases for Semantic Memory",
        "abstract": "Benchmarking vector databases as semantic memory backends for retrieval "
        "in language model applications.",
        "authors": ["F. Six"],
        "url": "http://arxiv.org/abs/2401.00005",
    },
    {
        "source": "arxiv",
        "source_id": "2401.00006",
        "title": "Forgetting and Consolidation in Continual Learning",
        "abstract": "Mechanisms of forgetting and memory consolidation for continual learning "
        "systems, with salience-based decay policies.",
        "authors": ["G. Seven"],
        "url": "http://arxiv.org/abs/2401.00006",
    },
]


class FakeArxivTool(BaseTool):
    name = "arxiv_search"
    description = "Offline fake arXiv tool for tests."
    side_effects = False

    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"query": {"type": "string"}}}

    def invoke(self, **kwargs: Any) -> ToolResult:
        limit = int(kwargs.get("limit", 20))
        return ToolResult(ok=True, data=_FAKE_PAPERS[:limit])


@pytest.fixture(scope="session")
def settings(tmp_path_factory) -> Settings:
    data_dir = tmp_path_factory.mktemp("researchos_data")
    return Settings(
        data_dir=data_dir,
        embedding_provider="local",
        embedding_dim=64,
        llm_provider="null",
        qdrant_mode="embedded",
    )


@pytest.fixture(scope="session")
def orch(settings):
    from researchos.orchestration.orchestrator import SequentialOrchestrator

    o = SequentialOrchestrator(settings)
    o.literature._tool = FakeArxivTool()  # inject offline tool
    return o
