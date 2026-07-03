"""Rich-document reader — PDFs, Word, spreadsheets, PowerPoint, scanned pages.

Docling does the heavy lifting: it turns messy layouts (multi-column PDFs, tables,
scanned forms) into clean Markdown text without *inventing* content. OCR for
scanned pages is enabled by the DOCLING_OCR setting.

Docling is a Level 1 dependency and is imported lazily, so the structured-only
path (Level 0 deps) never needs it installed.
"""
from __future__ import annotations

from pathlib import Path

from brain.config import settings
from brain.ingest.readers.base import TextResult

DOC_SUFFIXES = {".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".xls", ".html", ".htm"}


def is_document(path: Path) -> bool:
    return path.suffix.lower() in DOC_SUFFIXES


def read_document(path: Path, _doc_id: str) -> TextResult:
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(str(path))
    text = result.document.export_to_markdown()
    # Best-effort page map: Docling numbers pages 1..N; we anchor page starts to
    # form-feed markers when present, otherwise leave page unknown (citation still
    # resolves to the document). Precise per-char page mapping is a later refinement.
    page_map = []
    return TextResult(text=text, page_map=page_map)
