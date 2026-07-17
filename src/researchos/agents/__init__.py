"""Agents. Foundation ships Planner + Literature + Knowledge; Critic/Idea/Experiment/
Writing follow behind the same ``Agent`` interface (ARCHITECTURE.md §3)."""

from researchos.agents.base import BaseAgent
from researchos.agents.knowledge import KnowledgeAgent
from researchos.agents.literature import LiteratureAgent

__all__ = ["BaseAgent", "LiteratureAgent", "KnowledgeAgent"]
