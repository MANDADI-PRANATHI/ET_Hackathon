"""The 'brain' behind a one-setting switch: Gemini (free tier) or Ollama (offline).

Swapping providers is a single env change (LLM_PROVIDER). Nothing else in the
codebase needs to know which one is in use. Heavy SDKs are imported lazily so
this module loads even when only one provider's package is installed.
"""
from __future__ import annotations

from typing import List, Optional, Protocol

from brain.config import settings


class LLM(Protocol):
    """Minimal contract every provider implements."""

    def generate(self, prompt: str, system: Optional[str] = None) -> str: ...


class GeminiLLM:
    """Google Gemini via the free tier (online)."""

    def __init__(self) -> None:
        from google import genai

        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set — add it to .env")
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        from google.genai import types

        config = (
            types.GenerateContentConfig(system_instruction=system) if system else None
        )
        resp = self._client.models.generate_content(
            model=self._model, contents=prompt, config=config
        )
        return (resp.text or "").strip()


class OllamaLLM:
    """A model running fully offline on this machine via Ollama."""

    def __init__(self) -> None:
        import ollama

        self._client = ollama.Client(host=settings.ollama_base_url)
        self._model = settings.ollama_model

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        messages: List[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = self._client.chat(model=self._model, messages=messages)
        return resp["message"]["content"].strip()


def get_llm() -> LLM:
    """Return the configured provider."""
    provider = settings.llm_provider.lower()
    if provider == "gemini":
        return GeminiLLM()
    if provider == "ollama":
        return OllamaLLM()
    raise ValueError(
        f"Unknown LLM_PROVIDER '{settings.llm_provider}' (use 'gemini' or 'ollama')"
    )
