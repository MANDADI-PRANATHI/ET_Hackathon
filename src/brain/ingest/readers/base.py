"""Shared reader result types.

A reader returns one of two shapes:
  - StructuredResult — facts read straight from table columns (no AI), plus a
    readable one-line rendering of each row so structured data is *also* findable
    by meaning-search and keyword search.
  - TextResult — clean text with an optional page map, to be chunked and mined
    for facts (deterministically first, then AI for what's left in the prose).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from brain.schema import EdgeFact, NodeFact


@dataclass
class StructuredResult:
    nodes: List[NodeFact] = field(default_factory=list)
    edges: List[EdgeFact] = field(default_factory=list)
    row_texts: List[str] = field(default_factory=list)   # one readable line per row


@dataclass
class TextResult:
    text: str = ""
    # (char_offset, page_number) breakpoints; empty for single-page / unknown.
    page_map: List[Tuple[int, int]] = field(default_factory=list)
