"""Drawing / P&ID reader — the "computer vision" path.

A vision-capable model *looks at the image* and reads off what an engineer would:
equipment tags (P-101A), line numbers, and instrument tags. This is the drawing
digitisation the brief asks for, done pragmatically — we let a strong vision model
read the drawing rather than hand-building a symbol/line detector, which would eat
the whole timeline for marginal accuracy on a hackathon corpus.

Everything read here is stamped low-confidence and flagged needs_review, so a
quick human-confirm step (Level 3 UI) can approve tags before they are trusted.
The vision call is behind the same provider switch as the text brain, imported
lazily and injectable for testing.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from brain.config import settings
from brain.ingest.readers.base import TextResult

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}

# A vision function reads image bytes + a prompt and returns text.
VisionFn = Callable[[bytes, str], str]

_PROMPT = (
    "You are digitising an engineering drawing / P&ID. List every item you can "
    "read, one per line, as `TYPE: VALUE`. Use these types: EQUIPMENT_TAG (e.g. "
    "P-101A, V-204, PSV-110B), LINE_NUMBER, INSTRUMENT_TAG. Read only what is "
    "printed on the drawing — do not guess or invent tags. If unsure of a "
    "character, keep your best reading and it will be confirmed by a human."
)


def is_drawing(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES


def _default_vision_fn() -> VisionFn:
    """Build a vision callable for the configured provider (lazy imports)."""
    provider = settings.llm_provider.lower()

    if provider == "gemini":
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)

        def _gemini(image: bytes, prompt: str) -> str:
            resp = client.models.generate_content(
                model=settings.gemini_vision_model,
                contents=[
                    types.Part.from_bytes(data=image, mime_type="image/png"),
                    prompt,
                ],
            )
            return (resp.text or "").strip()

        return _gemini

    import ollama

    client = ollama.Client(host=settings.ollama_base_url)

    def _ollama(image: bytes, prompt: str) -> str:
        resp = client.chat(
            model=settings.ollama_vision_model,
            messages=[{"role": "user", "content": prompt, "images": [image]}],
        )
        return resp["message"]["content"].strip()

    return _ollama


def read_drawing(
    path: Path, _doc_id: str, vision_fn: Optional[VisionFn] = None
) -> TextResult:
    vision_fn = vision_fn or _default_vision_fn()
    image = Path(path).read_bytes()
    text = vision_fn(image, _PROMPT)
    return TextResult(text=text)
