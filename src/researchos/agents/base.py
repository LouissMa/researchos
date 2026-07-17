"""Base agent.

Enforces the core contract: an agent receives read-only ``ResearchState`` plus a
``Task`` and returns an ``AgentResult`` carrying a ``StateDelta`` — it never mutates
global state directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from researchos.core.state import AgentResult, ResearchState, StateDelta, Task


class BaseAgent(ABC):
    role: str = "agent"

    @abstractmethod
    def run(self, state: ResearchState, task: Task) -> AgentResult: ...

    def _result(
        self,
        *,
        output: str = "",
        delta: StateDelta | None = None,
        reasoning: list[str] | None = None,
        tool_calls: list[str] | None = None,
        ok: bool = True,
        error: str | None = None,
    ) -> AgentResult:
        return AgentResult(
            agent=self.role,
            output=output,
            delta=delta or StateDelta(),
            reasoning=reasoning or [],
            tool_calls=tool_calls or [],
            ok=ok,
            error=error,
        )
