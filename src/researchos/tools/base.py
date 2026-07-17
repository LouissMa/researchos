"""Tool base class and registry.

Concrete tools declare a name, whether they have side effects, and a JSON input schema,
then implement ``invoke``. The registry lets the planner/agents discover tools by name.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from researchos.core.interfaces import ToolResult


class BaseTool(ABC):
    name: str = "tool"
    description: str = ""
    side_effects: bool = False

    @abstractmethod
    def input_schema(self) -> dict[str, Any]:  # JSON-schema-like
        ...

    @abstractmethod
    def invoke(self, **kwargs: Any) -> ToolResult: ...


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> BaseTool:
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def names(self) -> list[str]:
        return list(self._tools)
