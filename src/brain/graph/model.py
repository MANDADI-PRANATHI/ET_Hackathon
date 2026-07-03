"""The merged, in-memory knowledge graph — built from staged facts.

Level 1 emits the *same* fact many times (an asset named in ten documents,
a work order that also names its asset). Level 2 merges those into one node per
real thing and one edge per real relationship, aggregating provenance and
confidence as it goes.

This model is deliberately storage-free and pure-Python, so the hard part —
correct merging, property precedence, confidence build-up, linkage metrics — is
fully testable without a database. The Neo4j writer (stores/graph_writer.py) just
persists whatever this model holds.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from brain.ingest.confidence import agreement_boost
from brain.schema import SourceRef, StagedDoc

# how much to trust a property value by the extractor that produced it
_EXTRACTOR_TIER = {"structured": 3, "regex": 2, "vision": 1, "ai": 1}


@dataclass
class MergedNode:
    label: str
    key: str
    value: str
    properties: Dict[str, object] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)
    extractors: List[str] = field(default_factory=list)
    sources: List[SourceRef] = field(default_factory=list)
    source_confidences: List[float] = field(default_factory=list)
    needs_review: bool = False
    # per-property tier, so a structured value is never overwritten by a guess
    _prop_tier: Dict[str, int] = field(default_factory=dict, repr=False)

    @property
    def confidence(self) -> float:
        """Built up from every source that asserted this node (agreement raises it)."""
        return round(agreement_boost(self.source_confidences), 4)

    @property
    def id(self) -> Tuple[str, str]:
        return (self.label, self.value)


@dataclass
class MergedEdge:
    type: str
    from_label: str
    from_value: str
    to_label: str
    to_value: str
    extractors: List[str] = field(default_factory=list)
    sources: List[SourceRef] = field(default_factory=list)
    source_confidences: List[float] = field(default_factory=list)
    needs_review: bool = False

    @property
    def confidence(self) -> float:
        return round(agreement_boost(self.source_confidences), 4)

    @property
    def id(self) -> Tuple[str, str, str, str, str]:
        return (self.type, self.from_label, self.from_value, self.to_label, self.to_value)


class GraphModel:
    def __init__(self) -> None:
        self.nodes: Dict[Tuple[str, str], MergedNode] = {}
        self.edges: Dict[tuple, MergedEdge] = {}

    # --- merging ----------------------------------------------------------

    def add_node(self, label, key, value, properties, source, confidence,
                 extractor, needs_review=False, aliases=None) -> MergedNode:
        nid = (label, value)
        node = self.nodes.get(nid)
        if node is None:
            node = MergedNode(label=label, key=key, value=value)
            self.nodes[nid] = node

        tier = _EXTRACTOR_TIER.get(extractor, 1)
        for pk, pv in (properties or {}).items():
            if pv in (None, ""):
                continue
            # Take a property only if the slot is empty or a *more trusted*
            # extractor is now supplying it.
            if node.properties.get(pk) in (None, "") or tier > node._prop_tier.get(pk, 0):
                node.properties[pk] = pv
                node._prop_tier[pk] = tier

        node.extractors.append(extractor)
        node.sources.append(source)
        node.source_confidences.append(confidence)
        for a in (aliases or []):
            if a and a not in node.aliases:
                node.aliases.append(a)
        # A node is only "needs review" if *nothing* trustworthy confirmed it.
        node.needs_review = all(
            e in ("vision",) for e in node.extractors
        ) and (needs_review or node.needs_review)
        return node

    def add_edge(self, type, from_label, from_value, to_label, to_value,
                 source, confidence, extractor, needs_review=False) -> MergedEdge:
        eid = (type, from_label, from_value, to_label, to_value)
        edge = self.edges.get(eid)
        if edge is None:
            edge = MergedEdge(type=type, from_label=from_label, from_value=from_value,
                              to_label=to_label, to_value=to_value)
            self.edges[eid] = edge
        edge.extractors.append(extractor)
        edge.sources.append(source)
        edge.source_confidences.append(confidence)
        edge.needs_review = edge.needs_review or needs_review
        return edge

    # --- convenience ------------------------------------------------------

    def nodes_by_label(self, label: str) -> List[MergedNode]:
        return [n for n in self.nodes.values() if n.label == label]

    def edges_from(self, label: str, value: str) -> List[MergedEdge]:
        return [e for e in self.edges.values()
                if e.from_label == label and e.from_value == value]

    def edges_to(self, label: str, value: str) -> List[MergedEdge]:
        return [e for e in self.edges.values()
                if e.to_label == label and e.to_value == value]

    def neighbours(self, label: str, value: str) -> List[MergedEdge]:
        return self.edges_from(label, value) + self.edges_to(label, value)


def build_graph(docs: List[StagedDoc]) -> GraphModel:
    """Merge every staged document into one asset-centric graph.

    Node values (and the endpoints of every edge) are canonicalised first, so
    variant surface forms collapse onto one node while genuinely distinct
    entities (P-101A vs P-101B) stay separate.
    """
    from brain.graph.resolve import canonical_value

    g = GraphModel()
    for d in docs:
        # The document itself is a node too.
        g.add_node("Document", "id", d.document.id,
                   {"id": d.document.id, "doc_type": d.document.doc_type,
                    "title": d.document.title, "path": d.document.path,
                    "source": d.document.source, "ingested_at": d.document.ingested_at},
                   SourceRef(doc_id=d.document.id, path=d.document.path),
                   1.0, "structured")
        for ch in d.chunks:
            g.add_node("Chunk", "id", ch.id,
                       {"id": ch.id, "text": ch.text, "page": ch.page,
                        "embedding": ch.embedding},
                       SourceRef(doc_id=d.document.id, path=d.document.path, page=ch.page),
                       1.0, "structured")
        for n in d.nodes:
            cval = canonical_value(n.label, n.value)
            props = dict(n.properties)
            if n.key in props:                    # keep the key property canonical too
                props[n.key] = cval
            aliases = list(n.aliases)
            if n.value != cval and n.value not in aliases:
                aliases.append(n.value)           # remember the original surface form
            g.add_node(n.label, n.key, cval, props, n.source,
                       n.confidence, n.extractor, n.needs_review, aliases)
        for e in d.edges:
            g.add_edge(e.type, e.from_label, canonical_value(e.from_label, e.from_value),
                       e.to_label, canonical_value(e.to_label, e.to_value),
                       e.source, e.confidence, e.extractor, e.needs_review)
    return g
