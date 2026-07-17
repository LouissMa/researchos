"""LLM abstraction over any OpenAI-compatible backend, with a null fallback."""

from researchos.llm.client import NullLLM, OpenAICompatibleLLM, get_llm

__all__ = ["get_llm", "NullLLM", "OpenAICompatibleLLM"]
