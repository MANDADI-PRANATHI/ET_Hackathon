"""The staging data model — the contract between Level 1 (extraction) and
Level 2 (graph build).

Everything a document yields is expressed as one of three things:
  - a **NodeFact**  (a dot in the graph: an Asset, WorkOrder, Regulation, ...)
  - an **EdgeFact**  (a link between two dots: MAINTAINS, GOVERNS, MENTIONS, ...)
  - a **Chunk**      (a searchable passage, carrying its own meaning-fingerprint later)

Every NodeFact and EdgeFact carries three things that make the whole system
trustworthy and auditable, no matter where the fact came from:
  - **source**      where in which document the fact was found (powers citations)
  - **confidence**  how sure we are (built up, never guessed — see confidence.py)
  - **extractor**   which method produced it (structured | regex | ai | vision)

Level 2 merges NodeFacts by (label, key, value) and creates the EdgeFacts,
so the graph builder never needs to know *how* a fact was extracted.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# --- how a fact was produced (drives base confidence; see confidence.py) ---
STRUCTURED = "structured"   # read directly from a table/spreadsheet column — no AI
REGEX = "regex"             # matched a deterministic identifier pattern — no AI
AI = "ai"                   # extracted from prose by the LLM, tied to a source sentence
VISION = "vision"           # read off a drawing/scan image by the vision model


class SourceRef(BaseModel):
    """Where a fact came from — the anchor for a clickable citation."""

    doc_id: str
    path: str
    page: Optional[int] = None
    evidence: Optional[str] = None          # the exact source sentence / cell, if any
    char_start: Optional[int] = None
    char_end: Optional[int] = None


class NodeFact(BaseModel):
    """One dot in the graph, keyed by (label, key -> value)."""

    label: str                               # e.g. "Asset", "WorkOrder"
    key: str                                 # the unique property name, e.g. "tag"
    value: str                               # the unique property value, e.g. "P-101A"
    properties: Dict[str, Any] = Field(default_factory=dict)
    source: SourceRef
    confidence: float = 1.0
    extractor: str = STRUCTURED
    needs_review: bool = False               # e.g. vision reads await human-confirm
    aliases: List[str] = Field(default_factory=list)  # alt surface forms (for L2 resolution)


class EdgeFact(BaseModel):
    """One link between two dots, identified by their (label, key, value)."""

    type: str                                # e.g. "MAINTAINS", "MENTIONS"
    from_label: str
    from_value: str
    to_label: str
    to_value: str
    source: SourceRef
    confidence: float = 1.0
    extractor: str = STRUCTURED
    needs_review: bool = False


class Chunk(BaseModel):
    """A searchable passage of a document (embedding is attached at build time)."""

    id: str
    doc_id: str
    text: str
    ordinal: int                             # position within the document
    page: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    embedding: Optional[List[float]] = None


class DocumentRecord(BaseModel):
    """The document itself — becomes a Document node in the graph."""

    id: str
    doc_type: str                            # PID | WorkOrder | IncidentReport | ...
    title: str
    path: str
    source: str = "corpus"
    ingested_at: Optional[str] = None


class StagedDoc(BaseModel):
    """Everything one document yields — written to data/staging/<id>.json."""

    document: DocumentRecord
    nodes: List[NodeFact] = Field(default_factory=list)
    edges: List[EdgeFact] = Field(default_factory=list)
    chunks: List[Chunk] = Field(default_factory=list)

    def write(self, staging_dir: Path) -> Path:
        staging_dir.mkdir(parents=True, exist_ok=True)
        out = staging_dir / f"{self.document.id}.json"
        out.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return out

    @classmethod
    def read(cls, path: Path) -> "StagedDoc":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_staging(staging_dir: Path) -> List[StagedDoc]:
    """Load every staged document from a staging directory."""
    staging_dir = Path(staging_dir)
    if not staging_dir.exists():
        return []
    return [StagedDoc.read(p) for p in sorted(staging_dir.glob("*.json"))]


def _counts(docs: List[StagedDoc]) -> Dict[str, int]:
    return {
        "documents": len(docs),
        "nodes": sum(len(d.nodes) for d in docs),
        "edges": sum(len(d.edges) for d in docs),
        "chunks": sum(len(d.chunks) for d in docs),
    }


def summarize_staging(staging_dir: Path) -> str:
    docs = load_staging(staging_dir)
    return json.dumps(_counts(docs))
