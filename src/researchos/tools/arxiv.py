"""arXiv search tool — a real client over the public arXiv Atom API. No key required.

This is the reference implementation of the ``Tool`` interface. Semantic Scholar,
OpenAlex, and GitHub tools will follow the same shape (ROADMAP Phase 1).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import feedparser
import httpx

from researchos.core.interfaces import ToolResult
from researchos.core.models import Paper
from researchos.tools.base import BaseTool

_ARXIV_API = "https://export.arxiv.org/api/query"


class ArxivTool(BaseTool):
    name = "arxiv_search"
    description = "Search arXiv for papers matching a query. Returns normalized Paper records."
    side_effects = False

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free-text search query"},
                "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                "sort_by": {
                    "type": "string",
                    "enum": ["relevance", "lastUpdatedDate", "submittedDate"],
                    "default": "relevance",
                },
            },
            "required": ["query"],
        }

    def invoke(self, **kwargs: Any) -> ToolResult:
        query: str = kwargs["query"]
        limit: int = int(kwargs.get("limit", 20))
        sort_by: str = kwargs.get("sort_by", "relevance")
        params: dict[str, str | int] = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": limit,
            "sortBy": sort_by,
            "sortOrder": "descending",
        }
        try:
            resp = httpx.get(
                _ARXIV_API, params=params, timeout=self._timeout, follow_redirects=True
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            return ToolResult(ok=False, error=f"arXiv request failed: {exc}")

        feed = feedparser.parse(resp.text)
        papers = [self._to_paper(e) for e in feed.entries]
        return ToolResult(ok=True, data=[p.model_dump() for p in papers])

    @staticmethod
    def _to_paper(entry: Any) -> Paper:
        source_id = entry.get("id", "").rsplit("/abs/", 1)[-1]
        published: date | None = None
        if getattr(entry, "published_parsed", None):
            t = entry.published_parsed
            published = date(t.tm_year, t.tm_mon, t.tm_mday)
        pdf_url = ""
        for link in entry.get("links", []):
            if link.get("type") == "application/pdf":
                pdf_url = link.get("href", "")
        authors = [a.get("name", "") for a in entry.get("authors", [])]
        categories = [t.get("term", "") for t in entry.get("tags", [])]
        return Paper(
            source="arxiv",
            source_id=source_id,
            title=entry.get("title", "").replace("\n", " ").strip(),
            abstract=entry.get("summary", "").replace("\n", " ").strip(),
            authors=authors,
            published=published,
            url=entry.get("link", ""),
            pdf_url=pdf_url,
            categories=categories,
        ).ensure_id()
