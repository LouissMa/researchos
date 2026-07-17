"""Source tools: offline unit checks + live (network-marked) smoke tests."""

import pytest

from researchos.tools.github import GitHubTool
from researchos.tools.openalex import OpenAlexTool, _reconstruct_abstract
from researchos.tools.semantic_scholar import SemanticScholarTool


def test_openalex_reconstructs_inverted_abstract():
    inverted = {"Memory": [0], "is": [1], "all": [2], "you": [3], "need": [4]}
    assert _reconstruct_abstract(inverted) == "Memory is all you need"
    assert _reconstruct_abstract(None) == ""


def test_source_tools_expose_schema():
    for tool in (SemanticScholarTool(), OpenAlexTool(), GitHubTool()):
        schema = tool.input_schema()
        assert schema["properties"]["query"]["type"] == "string"
        assert not tool.side_effects


@pytest.mark.network
def test_github_live_search():
    result = GitHubTool().invoke(query="llm agent memory", limit=2)
    if not result.ok:
        pytest.skip(f"GitHub unavailable: {result.error}")
    assert isinstance(result.data, list)
    if result.data:
        assert "url" in result.data[0]


@pytest.mark.network
def test_openalex_live_search():
    result = OpenAlexTool().invoke(query="large language model agents", limit=3)
    assert result.ok, result.error
    assert len(result.data) >= 1
    assert result.data[0]["source"] == "openalex"
    assert result.data[0]["title"]


@pytest.mark.network
def test_semantic_scholar_live_search():
    result = SemanticScholarTool().invoke(query="retrieval augmented generation", limit=3)
    # Semantic Scholar rate-limits aggressively without a key; tolerate that.
    if not result.ok:
        pytest.skip(f"Semantic Scholar unavailable: {result.error}")
    assert result.data[0]["source"] == "semantic_scholar"
