"""LLM clients.

``NullLLM`` is the default: it reports ``available = False`` so callers degrade to
heuristics instead of crashing when no key is configured. ``OpenAICompatibleLLM`` talks
to any OpenAI-compatible endpoint (OpenAI, vLLM, DeepSeek, Together, Ollama, ...).
"""

from __future__ import annotations

from researchos.config import Settings
from researchos.logging import get_logger

log = get_logger(__name__)


class NullLLM:
    name = "null"
    available = False

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        return ""


class OpenAICompatibleLLM:
    def __init__(self, settings: Settings) -> None:
        self.name = f"openai:{settings.llm_model}"
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self.available = False
        self._client = None
        if settings.openai_api_key:
            try:
                from openai import OpenAI

                self._client = OpenAI(
                    api_key=settings.openai_api_key, base_url=settings.llm_base_url
                )
                self.available = True
            except Exception as exc:
                log.warning("LLM unavailable: %s", exc)

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        if not self._client:
            return ""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
        )
        return (resp.choices[0].message.content or "").strip()


def get_llm(settings: Settings):
    """Factory. Returns a working OpenAI client if configured, else the null client."""
    if settings.llm_provider == "openai":
        client = OpenAICompatibleLLM(settings)
        if client.available:
            return client
        log.info("LLM provider 'openai' requested but no key found — using heuristic NullLLM.")
    return NullLLM()
