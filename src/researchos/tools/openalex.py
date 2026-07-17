"""OpenAlex search tool. Fully open, no key. A contact email enables the polite pool."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from researchos.core.interfaces import ToolResult
from researchos.core.models import Paper
from researchos.tools import http
from researchos.tools.base import BaseTool

_API = "https://api.openalex.org/works"


def _reconstruct_abstract(inverted: dict | None) -> str:
    """OpenAlex stores abstracts as an inverted index {word: [positions]}."""
    if not inverted:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort(key=lambda t: t[0])
    return " ".join(word for _, word in positions)


class OpenAlexTool(BaseTool):
    name = "openalex_search"
    description = "Search OpenAlex for works. Returns normalized Paper records."
    side_effects = False

    def __init__(self, mailto: str | None = None, timeout: float = 30.0) -> None:
        self._mailto = mailto
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
        params: dict[str, Any] = {"search": query, "per_page": limit}
        sort: str | None = kwargs.get("sort")  # e.g. "cited_by_count:desc"
        if sort:
            params["sort"] = sort
        if self._mailto:
            params["mailto"] = self._mailto
        try:
            resp = http.get(_API, params=params, timeout=self._timeout)
        except httpx.HTTPError as exc:
            return ToolResult(ok=False, error=f"OpenAlex request failed: {exc}")

        results = resp.json().get("results", []) or []
        papers = [self._to_paper(item) for item in results if item.get("display_name")]
        return ToolResult(ok=True, data=[p.model_dump() for p in papers])

    @staticmethod
    def _to_paper(item: dict) -> Paper:
        year = item.get("publication_year")
        published = date(year, 1, 1) if year else None
        doi = item.get("doi")
        if doi:
            doi = doi.replace("https://doi.org/", "")
        best_oa = item.get("best_oa_location") or {}
        primary = item.get("primary_location") or {}
        pdf = best_oa.get("pdf_url") or primary.get("pdf_url") or ""
        landing = primary.get("landing_page_url") or item.get("id", "")
        authors = [
            (a.get("author") or {}).get("display_name", "") for a in item.get("authorships") or []
        ]
        concepts = [c.get("display_name", "") for c in (item.get("concepts") or [])[:5]]
        return Paper(
            source="openalex",
            source_id=str(item.get("id", "")).rsplit("/", 1)[-1],
            title=item.get("display_name", "").strip(),
            abstract=_reconstruct_abstract(item.get("abstract_inverted_index")),
            authors=[a for a in authors if a],
            published=published,
            url=landing,
            pdf_url=pdf,
            categories=concepts,
            doi=doi,
            citation_count=item.get("cited_by_count"),
        ).ensure_id()
