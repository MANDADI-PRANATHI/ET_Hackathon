"""Rich-document reader — PDFs, Word, spreadsheets, PowerPoint, scanned pages.

Reading a born-digital file (real embedded text, not a photo of a page) is a
plain-code problem — pypdf/python-docx/python-pptx/openpyxl pull the text
straight out, no AI, no heavy ML models, a few MB total. That's the common
case and it's tried first, always installed, no addon needed.

Docling — a much heavier, optional dependency (pulls in torch/transformers
for layout analysis + OCR) — is only used as a fallback: legacy .doc/.xls,
.html/.htm, or when the light path finds no usable text (a scanned/
image-only page has no embedded text layer to extract).
"""
from __future__ import annotations

from pathlib import Path

from brain.ingest.readers.base import TextResult

DOC_SUFFIXES = {".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".xls", ".html", ".htm"}

# Below this many characters, treat light extraction as "found nothing usable"
# (most likely a scanned page with no embedded text layer) and fall back.
_LIGHT_MIN_CHARS = 40


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


def _read_with_docling(path: Path) -> TextResult:
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(str(path))
    text = result.document.export_to_markdown()
    # Best-effort page map: precise per-char page mapping is a later refinement;
    # citations resolve to the document, not the exact page, either way.
    return TextResult(text=text, page_map=[])


def read_document(path: Path, _doc_id: str) -> TextResult:
    light_fn = _LIGHT_READERS.get(path.suffix.lower())
    if light_fn is not None:
        try:
            text = light_fn(path)
        except Exception:
            text = ""
        if len(text.strip()) >= _LIGHT_MIN_CHARS:
            return TextResult(text=text, page_map=[])
    # Legacy .doc/.xls, .html/.htm, or the light path found nothing usable
    # (most likely a scanned page) — fall back to Docling.
    return _read_with_docling(path)
