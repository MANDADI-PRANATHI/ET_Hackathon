"""Route each file to the right reader and label its document type.

Document type comes from the corpus folder it sits in (that's the plant's own
filing); the reader is chosen by file kind. Structured tables and plain text need
no heavy dependencies; PDFs go through Docling; drawings go through the vision path.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from brain.ingest.readers import document, drawing, structured, text

# corpus folder name -> ontology document type
FOLDER_DOCTYPE = {
    "project_files": "ProjectFile",
    "work_orders": "WorkOrder",
    "inspections": "InspectionReport",
    "permits": "Permit",
    "quality_records": "QualityRecord",
    "incidents": "IncidentReport",
    "regulations": "Regulation",
    "manuals": "Manual",
    "procedures": "SOP",
    "operating_instructions": "OperatingInstruction",
    "drawings": "PID",
    "emails": "Email",
}

STRUCTURED, DRAWING, DOCUMENT, TEXT = "structured", "drawing", "document", "text"


@dataclass
class Route:
    path: Path
    doc_id: str
    doc_type: str
    reader_kind: str
    title: str


def _slug(rel: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9]+", "-", rel).strip("-").lower()
    digest = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:6]
    return f"{stem}-{digest}"


def _doc_type_for(path: Path, corpus_root: Path) -> str:
    try:
        rel_parts = path.relative_to(corpus_root).parts
    except ValueError:
        rel_parts = path.parts
    folder = rel_parts[0] if len(rel_parts) > 1 else ""
    return FOLDER_DOCTYPE.get(folder, "Document")


def _reader_kind_for(path: Path) -> str:
    if structured.is_structured(path):
        return STRUCTURED
    if drawing.is_drawing(path):
        return DRAWING
    if document.is_document(path):
        return DOCUMENT
    if text.is_plain(path):
        return TEXT
    return ""   # unsupported — skipped by the pipeline


def route(path: Path, corpus_root: Path) -> Route:
    path = Path(path)
    try:
        rel = str(path.relative_to(corpus_root))
    except ValueError:
        rel = path.name
    return Route(
        path=path,
        doc_id=_slug(rel),
        doc_type=_doc_type_for(path, corpus_root),
        reader_kind=_reader_kind_for(path),
        title=path.stem.replace("_", " ").title(),
    )
