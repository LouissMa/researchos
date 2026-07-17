"""GitHub repository search tool.

Used to find code implementations for papers. Works unauthenticated (low rate limit);
set ``GITHUB_TOKEN`` to raise limits. Returns lightweight repo records, not ``Paper``s.
"""

from __future__ import annotations

from typing import Any

import httpx

from researchos.core.interfaces import ToolResult
from researchos.tools import http
from researchos.tools.base import BaseTool

_API = "https://api.github.com/search/repositories"


class GitHubTool(BaseTool):
    name = "github_search"
    description = "Search GitHub repositories by query. Returns repos sorted by stars."
    side_effects = False

    def __init__(self, token: str | None = None, timeout: float = 30.0) -> None:
        self._token = token
        self._timeout = timeout

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 3, "minimum": 1, "maximum": 20},
            },
            "required": ["query"],
        }

    def invoke(self, **kwargs: Any) -> ToolResult:
        query: str = kwargs["query"]
        limit: int = int(kwargs.get("limit", 3))
        headers = {"Accept": "application/vnd.github+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            resp = http.get(
                _API,
                params={"q": query, "sort": "stars", "order": "desc", "per_page": limit},
                headers=headers,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            return ToolResult(ok=False, error=f"GitHub request failed: {exc}")

        items = resp.json().get("items", []) or []
        repos = [
            {
                "full_name": it.get("full_name", ""),
                "url": it.get("html_url", ""),
                "stars": it.get("stargazers_count", 0),
                "description": it.get("description") or "",
            }
            for it in items
        ]
        return ToolResult(ok=True, data=repos)
