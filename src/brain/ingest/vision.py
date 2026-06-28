"""Read engineering drawings / P&IDs / scanned pages with the vision model
(drawing digitisation). Returns the tags/lines it can see. Gemini path shown;
Ollama vision (qwen2.5vl) can be added the same way. Imported lazily.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

from brain.config import settings

PROMPT = (
    "This is an engineering drawing or P&ID. Read it and list every equipment tag, "
    "line number, and instrument tag you can see (e.g. P-101A, PSV-110B, FT-150). "
    'Return STRICT JSON only: {"tags": ["...", "..."]}'
)


def read_drawing(path: Path, mime_type: str = "image/png") -> Dict[str, List[str]]:
    if settings.llm_provider != "gemini":
        raise RuntimeError("Vision currently wired for Gemini; set LLM_PROVIDER=gemini")
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
    image_bytes = Path(path).read_bytes()
    resp = client.models.generate_content(
        model=settings.gemini_vision_model,
        contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime_type), PROMPT],
    )
    match = re.search(r"\{.*\}", resp.text or "", re.S)
    if not match:
        return {"tags": []}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"tags": []}
