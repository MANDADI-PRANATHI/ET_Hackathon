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

Passage retrieval is a **local hybrid search**: BM25 keyword matching and dense
embedding similarity are fused with Reciprocal Rank Fusion, then a local
cross-encoder reranker (if available) makes the final ordering call. All three
stages run on free, on-device models — no API call is needed to find the right
evidence. This is deliberate: the intelligence that matters most (finding and
ranking the correct facts) should not depend on a cloud model being reachable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
    retrieval_method: str = "keyword"    # keyword | dense | hybrid(+rerank)

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
    def load(cls, staging_dir, onto, embedder=None) -> "KnowledgeBase":
        docs = load_staging(Path(staging_dir))
        g = build_graph(docs)
        chunks: List[_ChunkRec] = []
        for d in docs:
            for ch in d.chunks:
                chunks.append(_ChunkRec(ch.id, d.document.id, d.document.doc_type,
                                        d.document.path, ch.page, ch.text, ch.embedding))
        kb = cls(g, chunks, onto)
        if embedder is not None:
            kb.ensure_embeddings(embedder)
        return kb

    def ensure_embeddings(self, embedder) -> int:
        """Compute embeddings for any chunk that doesn't already have one.

        Lets semantic search work immediately on a corpus staged without
        `--embeddings` — the vectors are computed once, in memory, at startup,
        entirely on-device. Returns how many chunks were embedded."""
        missing = [c for c in self.chunks if not c.embedding]
        if not missing:
            return 0
        vectors = embedder.embed([c.text for c in missing])
        for c, v in zip(missing, vectors):
            c.embedding = v
        return len(missing)

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

    @staticmethod
    def _rrf_fuse(rank_lists: List[List[str]], k: int = 60) -> Dict[str, float]:
        """Reciprocal Rank Fusion: combine multiple ranked lists into one score
        per item, without needing the lists' raw scores to be comparable —
        exactly the situation with BM25 scores vs cosine similarities."""
        scores: Dict[str, float] = {}
        for ranks in rank_lists:
            for i, cid in enumerate(ranks):
                scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + i + 1)
        return scores

    def search_passages(self, question: str, top_k: int = 5,
                        embedder=None, reranker=None, pool_size: int = 0) -> List[Evidence]:
        """Local hybrid search: BM25 + dense embeddings fused by RRF, then an
        optional local cross-encoder reranks the fused pool. No API call
        anywhere in this method — every stage runs on-device."""
        pool_size = pool_size or max(top_k * 4, 20)
        by_id = {c.chunk_id: c for c in self.chunks}
        rank_lists: List[List[str]] = []

        kw_hits, _ms = self._kw.search(question, top_k=pool_size)
        if kw_hits:
            rank_lists.append([h.chunk_id for h in kw_hits])

        have_vectors = embedder is not None and any(c.embedding for c in self.chunks)
        if have_vectors:
            qv = embedder.embed([question])[0]
            dense_hits = self._cosine_search(qv, pool_size)
            if dense_hits:
                rank_lists.append([c.chunk_id for c, _s in dense_hits])

        if not rank_lists:
            return []

        fused = self._rrf_fuse(rank_lists)
        candidate_ids = sorted(fused, key=lambda cid: fused[cid], reverse=True)[:pool_size]

        method = ("hybrid" if len(rank_lists) > 1 else
                 ("dense" if have_vectors else "keyword"))
        if reranker is not None and candidate_ids:
            final_ids, conf = self._rerank(question, candidate_ids, by_id, reranker, top_k)
            method += "+rerank"
        else:
            final_ids = candidate_ids[:top_k]
            conf = self._normalize(fused, final_ids)

        ev: List[Evidence] = []
        for cid in final_ids:
            c = by_id[cid]
            ev.append(Evidence(statement=c.text,
                               source=SourceRef(doc_id=c.doc_id, path=c.path,
                                                page=c.page, evidence=c.text[:280]),
                               confidence=conf.get(cid, 0.0), kind="passage",
                               doc_type=c.doc_type, score=conf.get(cid, 0.0)))
        self._last_retrieval_method = method
        return ev

    @staticmethod
    def _normalize(fused: Dict[str, float], ids: List[str]) -> Dict[str, float]:
        vals = [fused[i] for i in ids]
        if not vals:
            return {}
        lo, hi = min(vals), max(vals)
        if hi <= lo:
            return {i: 1.0 for i in ids}
        return {i: round((fused[i] - lo) / (hi - lo), 3) for i in ids}

    @staticmethod
    def _rerank(question, candidate_ids, by_id, reranker, top_k) -> Tuple[List[str], Dict[str, float]]:
        """Cross-encoder rerank of the fused candidate pool; falls back to the
        fused order if the reranker errors on an unexpected input."""
        docs = [by_id[cid].text for cid in candidate_ids]
        text_to_id: Dict[str, str] = {}
        for cid in candidate_ids:
            text_to_id.setdefault(by_id[cid].text, cid)
        try:
            ranked = reranker.rerank(question, docs, top_k=len(docs))
        except Exception:  # noqa: BLE001 - a reranker hiccup must not break retrieval
            return candidate_ids[:top_k], {cid: 1.0 for cid in candidate_ids[:top_k]}
        ordered_ids = [text_to_id[t] for t, _s in ranked if t in text_to_id][:top_k]

        def sigmoid(x: float) -> float:
            return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))

        conf = {text_to_id[t]: round(sigmoid(float(s)), 3)
               for t, s in ranked if t in text_to_id}
        return ordered_ids, conf

    # --- combined ---------------------------------------------------------

    def retrieve(self, question: str, top_k: int = 5, embedder=None, reranker=None) -> Retrieved:
        assets = self.spot_assets(question)
        graph_ev: List[Evidence] = []
        for a in assets:
            graph_ev.extend(self.asset_facts(a))
        passages = self.search_passages(question, top_k=top_k, embedder=embedder,
                                        reranker=reranker)
        return Retrieved(question=question, assets=assets,
                         graph_evidence=graph_ev, passage_evidence=passages,
                         retrieval_method=getattr(self, "_last_retrieval_method", "keyword"))
