"""The 'traditional search' baseline — in-memory BM25 over document passages.

This is the honest opponent we measure the copilot against for the brief's
"time-to-answer vs. traditional search" metric. It also exposes *why* keyword
search struggles: it matches words, not meaning, and it has no idea that a
maintenance question might be answered by a safety document. Pure stdlib, so it
runs with only Level 0 dependencies.
"""
from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_TOKEN = re.compile(r"[a-z0-9][a-z0-9\-/\.]*")


def tokenize(text: str) -> List[str]:
    toks = _TOKEN.findall((text or "").lower())
    return [t.strip("-./") for t in toks if t.strip("-./")]


@dataclass
class _Doc:
    chunk_id: str
    doc_id: str
    text: str
    length: int
    tf: Dict[str, int]


@dataclass
class SearchHit:
    chunk_id: str
    doc_id: str
    text: str
    score: float


@dataclass
class KeywordIndex:
    """A minimal BM25 index (k1, b are the usual defaults)."""

    k1: float = 1.5
    b: float = 0.75
    _docs: List[_Doc] = field(default_factory=list)
    _df: Dict[str, int] = field(default_factory=dict)
    _avgdl: float = 0.0

    def add(self, chunk_id: str, text: str, doc_id: str = "") -> None:
        toks = tokenize(text)
        tf: Dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        self._docs.append(_Doc(chunk_id, doc_id, text, len(toks), tf))
        for term in tf:
            self._df[term] = self._df.get(term, 0) + 1

    def finalize(self) -> "KeywordIndex":
        n = len(self._docs)
        self._avgdl = (sum(d.length for d in self._docs) / n) if n else 0.0
        return self

    def _idf(self, term: str) -> float:
        n = len(self._docs)
        df = self._df.get(term, 0)
        # BM25 idf with the usual +0.5 smoothing (floored at 0).
        return max(0.0, math.log((n - df + 0.5) / (df + 0.5) + 1.0))

    def search(self, query: str, top_k: int = 5) -> Tuple[List[SearchHit], float]:
        """Return (hits, elapsed_ms). Timing is what the scorecard compares."""
        start = time.perf_counter()
        q_terms = tokenize(query)
        scored: List[SearchHit] = []
        for d in self._docs:
            score = 0.0
            for term in q_terms:
                if term not in d.tf:
                    continue
                freq = d.tf[term]
                denom = freq + self.k1 * (1 - self.b + self.b * d.length / (self._avgdl or 1))
                score += self._idf(term) * (freq * (self.k1 + 1)) / (denom or 1)
            if score > 0:
                scored.append(SearchHit(d.chunk_id, d.doc_id, d.text, round(score, 4)))
        scored.sort(key=lambda h: h.score, reverse=True)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return scored[:top_k], elapsed_ms

    def __len__(self) -> int:
        return len(self._docs)


def build_from_staging(staging_dir: Path) -> KeywordIndex:
    from brain.schema import load_staging

    index = KeywordIndex()
    for doc in load_staging(Path(staging_dir)):
        for ch in doc.chunks:
            index.add(ch.id, ch.text, doc_id=doc.document.id)
    return index.finalize()
