"""Semantic Scholar search tool (Graph API). No key required, but a key raises limits.

Set ``SEMANTIC_SCHOLAR_API_KEY`` to use the authenticated, higher-rate endpoint.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from researchos.core.interfaces import ToolResult
from researchos.core.models import Paper
from researchos.tools import http
from researchos.tools.base import BaseTool

_API = "https://api.semanticscholar.org/graph/v1/paper/search"
_FIELDS = "title,abstract,authors,year,externalIds,url,openAccessPdf,citationCount,fieldsOfStudy"


class SemanticScholarTool(BaseTool):
    name = "semantic_scholar_search"
    description = "Search Semantic Scholar for papers. Returns normalized Paper records."
    side_effects = False

    def __init__(self, api_key: str | None = None, timeout: float = 30.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
            },
            "required": ["query"],
        }

    def invoke(self, **kwargs: Any) -> ToolResult:
        query: str = kwargs["query"]
        limit: int = int(kwargs.get("limit", 20))
        headers = {"x-api-key": self._api_key} if self._api_key else None
        try:
            resp = http.get(
                _API,
                params={"query": query, "limit": limit, "fields": _FIELDS},
                headers=headers,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            return ToolResult(ok=False, error=f"Semantic Scholar request failed: {exc}")

        data = resp.json().get("data", []) or []
        papers = [self._to_paper(item) for item in data if item.get("title")]
        return ToolResult(ok=True, data=[p.model_dump() for p in papers])

    @staticmethod
    def _to_paper(item: dict) -> Paper:
        external = item.get("externalIds") or {}
        year = item.get("year")
        published = date(year, 1, 1) if year else None
        pdf = (item.get("openAccessPdf") or {}).get("url", "") or ""
        authors = [a.get("name", "") for a in item.get("authors") or []]
        return Paper(
            source="semantic_scholar",
            source_id=str(item.get("paperId", "")),
            title=item.get("title", "").strip(),
            abstract=(item.get("abstract") or "").strip(),
            authors=authors,
            published=published,
            url=item.get("url", "") or "",
            pdf_url=pdf,
            categories=item.get("fieldsOfStudy") or [],
            doi=external.get("DOI"),
            citation_count=item.get("citationCount"),
        ).ensure_id()
