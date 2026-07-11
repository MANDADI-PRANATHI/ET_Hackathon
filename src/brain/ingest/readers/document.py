"""Rich-document reader — PDFs, Word, spreadsheets, PowerPoint, scanned pages.

Reading a born-digital file (real embedded text, not a photo of a page) is a
plain-code problem — pypdf/python-docx/python-pptx/openpyxl pull the text
straight out, no AI, no heavy ML models, a few MB total. That's the common
case and it's tried first, always installed, no addon needed.

For a scanned PDF (no embedded text layer), a photo of a page IS an image —
so if a vision-capable LLM is already configured (Gemini, or Ollama's vision
model), we read it the same way a drawing/P&ID is read: render the page and
ask the vision model, reusing brain.ingest.readers.drawing's provider switch.
No new dependency for the *model* — just PyMuPDF (fitz) to rasterize a PDF
page to an image, which is lightweight (no ML weights, unlike Docling).

Docling — a much heavier, optional dependency (pulls in torch/transformers
for its own layout analysis + OCR) — is now the last resort: legacy
.doc/.xls/.html, or a scanned PDF when no vision LLM is configured at all.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from brain.config import settings
from brain.ingest.readers.base import TextResult

DOC_SUFFIXES = {".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".xls", ".html", ".htm"}

# Below this many characters, treat light extraction as "found nothing usable"
# (most likely a scanned page with no embedded text layer) and fall back.
_LIGHT_MIN_CHARS = 40

# Cap on pages sent through the vision model per scanned PDF — a vision call
# per page adds up fast against a free-tier quota (Gemini: 20/day).
_MAX_VISION_PAGES = 5

_SCAN_PROMPT = (
    "Transcribe all readable text from this scanned document page, as plain "
    "text, preserving paragraph breaks. Read only what is printed — do not "
    "guess or invent content you can't read clearly."
)


def is_document(path: Path) -> bool:
    return path.suffix.lower() in DOC_SUFFIXES


def _read_pdf_light(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


def _read_docx_light(path: Path) -> str:
    import docx

    d = docx.Document(str(path))
    parts = [p.text for p in d.paragraphs if p.text]
    for table in d.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def _read_pptx_light(path: Path) -> str:
    from pptx import Presentation

    prs = Presentation(str(path))
    parts = []
    for i, slide in enumerate(prs.slides, start=1):
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False) and shape.text_frame.text:
                parts.append(f"[Slide {i}] {shape.text_frame.text}")
    return "\n".join(parts)


def _read_xlsx_light(path: Path) -> str:
    import openpyxl

    wb = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    parts = []
    for ws in wb.worksheets:
        parts.append(f"[Sheet: {ws.title}]")
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


_LIGHT_READERS = {
    ".pdf": _read_pdf_light,
    ".docx": _read_docx_light,
    ".pptx": _read_pptx_light,
    ".xlsx": _read_xlsx_light,
}


def _vision_configured() -> bool:
    if settings.llm_provider.lower() == "gemini":
        return bool(settings.gemini_api_key)
    return settings.llm_provider.lower() == "ollama"


def _read_scanned_pdf_via_vision(path: Path) -> Optional[str]:
    """Render each page to an image and read it with the same vision model
    used for drawings. Returns None (caller falls back to Docling) if no
    vision LLM is configured, or the render/vision call fails."""
    if not _vision_configured():
        return None
    try:
        import fitz  # PyMuPDF

        from brain.ingest.readers.drawing import _default_vision_fn

        vision_fn = _default_vision_fn()
        parts = []
        with fitz.open(str(path)) as doc:
            for page in list(doc)[:_MAX_VISION_PAGES]:
                image_bytes = page.get_pixmap(dpi=200).tobytes("png")
                text = vision_fn(image_bytes, _SCAN_PROMPT)
                if text:
                    parts.append(text)
        return "\n\n".join(parts) if parts else None
    except Exception:
        return None


def _read_with_docling(path: Path) -> TextResult:
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(str(path))
    text = result.document.export_to_markdown()
    # Best-effort page map: precise per-char page mapping is a later refinement;
    # citations resolve to the document, not the exact page, either way.
    return TextResult(text=text, page_map=[])


def read_document(path: Path, _doc_id: str) -> TextResult:
    suffix = path.suffix.lower()
    light_fn = _LIGHT_READERS.get(suffix)
    if light_fn is not None:
        try:
            text = light_fn(path)
        except Exception:
            text = ""
        if len(text.strip()) >= _LIGHT_MIN_CHARS:
            return TextResult(text=text, page_map=[])

    if suffix == ".pdf":
        vision_text = _read_scanned_pdf_via_vision(path)
        if vision_text and len(vision_text.strip()) >= _LIGHT_MIN_CHARS:
            return TextResult(text=vision_text, page_map=[], extractor_hint="vision")

    # Legacy .doc/.xls, .html/.htm, or a scanned PDF with no vision LLM
    # configured at all — the true last resort.
    return _read_with_docling(path)
