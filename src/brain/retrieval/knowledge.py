"""The knowledge base the copilot reasons over — graph + passages together.

This is the heart of GraphRAG. A question is answered by using BOTH:
  1. the **graph** — spot the asset(s) the question is about, jump to their hub,
     and pull in the connected facts (work orders, inspections, incidents,
     governing procedures and regulations). This is what lets an answer cross
     department boundaries — a maintenance question reaching a safety document.
  2. **meaning search** — pull the passages whose *meaning* matches the question,
     even when they share no keywords.

Every piece of evidence carries its source and confidence, so the copilot can
cite it and score the answer. Runs on the in-memory GraphModel built from
staging, so the whole copilot works offline and is fully testable; a
Neo4j-backed knowledge base can later implement the same surface.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from brain.graph.model import GraphModel, build_graph
from brain.ingest.patterns import from_ontology
from brain.schema import SourceRef, load_staging

# Everyday words that refer to an equipment class, so "the relief valves" reaches
# every Valve-class asset even though no tag or exact name was typed.
_CLASS_SYNONYMS = {
    "pump": "Pump", "pumps": "Pump",
    "valve": "Valve", "valves": "Valve", "relief valve": "Valve",
    "relief valves": "Valve", "safety valve": "Valve", "safety valves": "Valve",
    "psv": "Valve",
    "vessel": "Vessel", "vessels": "Vessel", "drum": "Vessel",
    "exchanger": "HeatExchanger", "heat exchanger": "HeatExchanger",
    "compressor": "Compressor", "compressors": "Compressor",
    "transmitter": "Instrument", "instrument": "Instrument",
    "tank": "Tank", "column": "Column",
}


@dataclass
class Evidence:
    """One citable fact, from the graph or a passage."""

    statement: str
    source: SourceRef
    confidence: float
    kind: str                      # "graph" | "passage"
    doc_type: str = ""             # the department/type it came from
    score: float = 0.0             # retrieval score (passages)


@dataclass
class Retrieved:
    question: str
    assets: List[str] = field(default_factory=list)
    graph_evidence: List[Evidence] = field(default_factory=list)
    passage_evidence: List[Evidence] = field(default_factory=list)

    @property
    def all(self) -> List[Evidence]:
        return self.graph_evidence + self.passage_evidence


# --- rendering graph facts into cited statements ---------------------------

def _p(node, *keys, default="?"):
    for k in keys:
        v = node.properties.get(k) if node else None
        if v not in (None, ""):
            return v
    return default


def _render(edge, other) -> str:
    """A human-readable statement for one graph relationship."""
    t = edge.type
    if t == "MAINTAINS":
        return (f"Work order {_p(other,'wo_number')}: {_p(other,'action')} "
                f"({_p(other,'status')}) on {_p(other,'date')}, by {_p(other,'performed_by')}.")
    if t == "INSPECTS":
        return (f"Inspection {_p(other,'inspection_id')} ({_p(other,'type')}): "
                f"result {_p(other,'result')}, last done {_p(other,'last_inspection_date')}.")
    if t == "FOR_WORK_ON":
        return (f"Permit {_p(other,'permit_no')} ({_p(other,'work_type')}): "
                f"{_p(other,'status')}, issued {_p(other,'issue_date')}.")
    if t == "RAISED_AGAINST":
        return (f"Non-conformance {_p(other,'id')}: {_p(other,'finding')} "
                f"({_p(other,'status')}), raised {_p(other,'raised_date')}.")
    if t == "INVOLVES":
        return f"Incident {_p(other,'id')}: {_p(other,'title','name')} ({_p(other,'severity')})."
    if t == "AFFECTS":
        return f"Failure mode: {_p(other,'name')}."
    if t == "GOVERNS":
        return f"Governed by {_p(other,'title','id','code')}."
    if t == "ABOUT":
        return f"Documented in '{_p(other,'title')}' ({_p(other,'doc_type')})."
    if t == "LOCATED_IN":
        return f"Located in unit {_p(other,'name')}."
    if t == "HAS_PARAMETER":
        return f"Parameter {_p(other,'name')} = {_p(other,'setpoint')} {_p(other,'unit','')}."
    if t == "PERFORMED":
        return f"{_p(other,'name','id')} performed the work."
    return f"{t} {other.label if other else ''}."


@dataclass
class _ChunkRec:
    chunk_id: str
    doc_id: str
    doc_type: str
    path: str
    page: Optional[int]
    text: str
    embedding: Optional[List[float]]


class KnowledgeBase:
    def __init__(self, graph: GraphModel, chunks: List[_ChunkRec], onto: dict):
        self.g = graph
        self.chunks = chunks
        self.onto = onto
        self._px = from_ontology(onto)
        self._asset_names = {n.value: (n.properties.get("name") or "").lower()
                             for n in graph.nodes_by_label("Asset")}
        self._asset_class = {n.value: (n.properties.get("asset_class") or "")
                             for n in graph.nodes_by_label("Asset")}
        from brain.search.keyword import KeywordIndex
        self._kw = KeywordIndex()
        for c in chunks:
            self._kw.add(c.chunk_id, c.text, doc_id=c.doc_id)
        self._kw.finalize()

    # --- construction -----------------------------------------------------

    @classmethod
    def load(cls, staging_dir, onto) -> "KnowledgeBase":
        docs = load_staging(Path(staging_dir))
        g = build_graph(docs)
        chunks: List[_ChunkRec] = []
        for d in docs:
            for ch in d.chunks:
                chunks.append(_ChunkRec(ch.id, d.document.id, d.document.doc_type,
                                        d.document.path, ch.page, ch.text, ch.embedding))
        return cls(g, chunks, onto)

    # --- graph side -------------------------------------------------------

    def spot_assets(self, question: str) -> List[str]:
        """Find which assets the question is about (tags, then names)."""
        found: List[str] = []
        for m in self._px.find(question, "equipment_tag"):
            if ("Asset", m.normalized) in self.g.nodes and m.normalized not in found:
                found.append(m.normalized)
        q = question.lower()
        for value, name in self._asset_names.items():
            if value in found:
                continue
            if name and name in q:
                found.append(value)
        # Only when no specific asset was named, let category words ("the relief
        # valves") reach every asset of that class — so a precise tag query stays
        # precise instead of expanding to the whole class.
        if not found:
            classes = {cls for syn, cls in _CLASS_SYNONYMS.items() if syn in q}
            for value, cls in self._asset_class.items():
                if cls in classes and value not in found:
                    found.append(value)
        return found

    def asset_facts(self, asset_value: str, limit: int = 40) -> List[Evidence]:
        ev: List[Evidence] = []
        for edge in self.g.neighbours("Asset", asset_value):
            other_is_from = edge.from_label != "Asset" or edge.from_value != asset_value
            other_key = ((edge.from_label, edge.from_value) if other_is_from
                         else (edge.to_label, edge.to_value))
            other = self.g.nodes.get(other_key)
            if other is not None and other.label == "Chunk":
                continue                          # chunks are covered by passage search
            src = edge.sources[0] if edge.sources else SourceRef(doc_id="", path="")
            ev.append(Evidence(statement=_render(edge, other), source=src,
                               confidence=edge.confidence, kind="graph",
                               doc_type=(other.properties.get("doc_type", "")
                                         if other else "")))
        ev.sort(key=lambda e: e.confidence, reverse=True)
        return ev[:limit]

    # --- meaning search ---------------------------------------------------

    def _cosine_search(self, query_vec, top_k):
        def cos(a, b):
            return sum(x * y for x, y in zip(a, b))   # embeddings are normalised
        scored = [(c, cos(query_vec, c.embedding)) for c in self.chunks if c.embedding]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def search_passages(self, question: str, top_k: int = 5,
                        embedder=None) -> List[Evidence]:
        have_vectors = embedder is not None and any(c.embedding for c in self.chunks)
        ev: List[Evidence] = []
        if have_vectors:
            qv = embedder.embed([question])[0]
            for c, score in self._cosine_search(qv, top_k):
                ev.append(Evidence(statement=c.text,
                                   source=SourceRef(doc_id=c.doc_id, path=c.path,
                                                    page=c.page, evidence=c.text[:280]),
                                   confidence=round(min(1.0, max(0.0, score)), 3),
                                   kind="passage", doc_type=c.doc_type, score=round(score, 3)))
        else:
            hits, _ms = self._kw.search(question, top_k=top_k)
            by_id = {c.chunk_id: c for c in self.chunks}
            top = hits[0].score if hits else 1.0
            for h in hits:
                c = by_id.get(h.chunk_id)
                if not c:
                    continue
                ev.append(Evidence(statement=c.text,
                                   source=SourceRef(doc_id=c.doc_id, path=c.path,
                                                    page=c.page, evidence=c.text[:280]),
                                   confidence=round(h.score / top, 3) if top else 0.0,
                                   kind="passage", doc_type=c.doc_type, score=h.score))
        return ev

    # --- combined ---------------------------------------------------------

    def retrieve(self, question: str, top_k: int = 5, embedder=None) -> Retrieved:
        assets = self.spot_assets(question)
        graph_ev: List[Evidence] = []
        for a in assets:
            graph_ev.extend(self.asset_facts(a))
        passages = self.search_passages(question, top_k=top_k, embedder=embedder)
        return Retrieved(question=question, assets=assets,
                         graph_evidence=graph_ev, passage_evidence=passages)
