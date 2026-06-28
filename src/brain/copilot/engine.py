"""The copilot entry point: ask(question) -> grounded answer + sources + confidence."""
from __future__ import annotations

from typing import Any, Dict

from brain.copilot.answer import answer_question
from brain.copilot.retrieve import retrieve


def ask(question: str, k: int = 6) -> Dict[str, Any]:
    return answer_question(retrieve(question, k=k))
