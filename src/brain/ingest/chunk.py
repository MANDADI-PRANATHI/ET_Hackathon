"""Split a document into searchable passages ("chunks").

Paragraph-aware windowing: we group whole paragraphs up to a target size with a
little overlap, so a passage rarely cuts a sentence in half and neighbouring
passages share context. Each chunk keeps its character span (and page, if known)
so a retrieved passage can point back to the exact spot in the document.
"""
from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

from brain.schema import Chunk

_PARA = re.compile(r"\n\s*\n")


def _paragraphs(text: str) -> List[Tuple[int, int]]:
    """Return (start, end) spans of non-empty paragraphs."""
    spans: List[Tuple[int, int]] = []
    cursor = 0
    for m in _PARA.finditer(text):
        if text[cursor : m.start()].strip():
            spans.append((cursor, m.start()))
        cursor = m.end()
    if text[cursor:].strip():
        spans.append((cursor, len(text)))
    return spans


def _page_for(offset: int, page_map: Optional[Sequence[Tuple[int, int]]]) -> Optional[int]:
    """Given (char_offset, page) breakpoints, find the page a char offset sits on."""
    if not page_map:
        return None
    page = page_map[0][1]
    for start, pg in page_map:
        if offset >= start:
            page = pg
        else:
            break
    return page


def chunk_text(
    doc_id: str,
    text: str,
    target_chars: int = 800,
    overlap_chars: int = 120,
    page_map: Optional[Sequence[Tuple[int, int]]] = None,
) -> List[Chunk]:
    text = text or ""
    if not text.strip():
        return []

    chunks: List[Chunk] = []
    ordinal = 0
    paras = _paragraphs(text)
    i = 0
    while i < len(paras):
        start = paras[i][0]
        end = paras[i][1]
        j = i + 1
        # Grow the window by whole paragraphs until we reach the target size.
        while j < len(paras) and (paras[j][1] - start) <= target_chars:
            end = paras[j][1]
            j += 1
        passage = text[start:end].strip()
        if passage:
            chunks.append(
                Chunk(
                    id=f"{doc_id}::c{ordinal}",
                    doc_id=doc_id,
                    text=passage,
                    ordinal=ordinal,
                    page=_page_for(start, page_map),
                    char_start=start,
                    char_end=end,
                )
            )
            ordinal += 1
        if j <= i:                     # safety: always advance
            j = i + 1
        # Step back a little for overlap, but never re-emit the same paragraph.
        if j < len(paras) and overlap_chars > 0 and (j - 1) > i:
            back_target = end - overlap_chars
            k = j - 1
            while k > i and paras[k][0] > back_target:
                k -= 1
            i = max(k, i + 1)
        else:
            i = j
    return chunks
