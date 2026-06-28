"""Plain data structures for extracted facts. Every fact carries WHERE it came
from (source) and HOW confident the extraction was (confidence) + the method
that produced it — this is what later feeds the trustworthy confidence score.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExtractedEntity:
    label: str                       # ontology node label, e.g. "Asset"
    key: str                         # unique identifier, e.g. "P-101A"
    properties: Dict[str, Any] = field(default_factory=dict)
    source: str = ""                 # file + locator / evidence quote
    confidence: float = 1.0
    method: str = "rule"             # rule | structured | ai | vision


@dataclass
class ExtractedRelation:
    type: str
    from_label: str
    from_key: str
    to_label: str
    to_key: str
    source: str = ""
    confidence: float = 1.0
    method: str = "rule"


@dataclass
class Chunk:
    id: str
    text: str
    page: Optional[int] = None
    embedding: Optional[List[float]] = None


@dataclass
class DocFacts:
    document_id: str
    doc_type: str
    path: str
    entities: List[ExtractedEntity] = field(default_factory=list)
    relations: List[ExtractedRelation] = field(default_factory=list)
    chunks: List[Chunk] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
