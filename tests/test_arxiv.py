"""Live arXiv tool test. Marked `network` — run with `pytest -m network`."""

import pytest

from researchos.tools.arxiv import ArxivTool


def test_arxiv_input_schema():
    schema = ArxivTool().input_schema()
    assert schema["properties"]["query"]["type"] == "string"
    assert "query" in schema["required"]


@pytest.mark.network
def test_arxiv_live_search_returns_papers():
    result = ArxivTool().invoke(query="large language model agents", limit=3)
    assert result.ok, result.error
    assert len(result.data) >= 1
    first = result.data[0]
    assert first["source"] == "arxiv"
    assert first["title"]
    assert first["id"]
