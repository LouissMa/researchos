"""Build the configured set of search tools."""

from __future__ import annotations

from researchos.config import Settings
from researchos.logging import get_logger
from researchos.tools.arxiv import ArxivTool
from researchos.tools.base import BaseTool
from researchos.tools.openalex import OpenAlexTool
from researchos.tools.semantic_scholar import SemanticScholarTool

log = get_logger(__name__)


def build_search_tools(settings: Settings) -> list[BaseTool]:
    """Instantiate the source tools named in ``settings.sources`` (order preserved)."""
    tools: list[BaseTool] = []
    for name in settings.source_list:
        if name == "arxiv":
            tools.append(ArxivTool())
        elif name == "semantic_scholar":
            tools.append(SemanticScholarTool(api_key=settings.semantic_scholar_api_key))
        elif name == "openalex":
            tools.append(OpenAlexTool(mailto=settings.openalex_mailto))
        else:
            log.warning("Unknown source %r — skipping", name)
    if not tools:
        log.warning("No valid sources configured — defaulting to arXiv.")
        tools.append(ArxivTool())
    return tools
