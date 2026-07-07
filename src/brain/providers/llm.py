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
        import re
        import time

        from google.genai import types

        config = (
            types.GenerateContentConfig(system_instruction=system) if system else None
        )
        last_error: Exception = RuntimeError("Gemini call never attempted")
        # Free-tier rate limits (429 RESOURCE_EXHAUSTED) are transient — retry a
        # bounded number of times with the server's suggested delay, then give
        # up. copilot/answer.py catches the final error and falls back to the
        # extractive answer, so this only needs to smooth over short blips —
        # not retry forever.
        for _ in range(3):
            try:
                resp = self._client.models.generate_content(
                    model=self._model, contents=prompt, config=config
                )
                return (resp.text or "").strip()
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                if "RESOURCE_EXHAUSTED" not in msg and "429" not in msg:
                    raise
                last_error = e
                m = re.search(r"retry(?:Delay)?['\":\s]*([0-9]+(?:\.[0-9]+)?)\s*s", msg)
                delay = (float(m.group(1)) + 2) if m else 15.0
                time.sleep(min(delay, 20))
        raise last_error


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
