"""Level 2 regression tests — graph merge, entity resolution, metrics, export.

Pure logic, no database. Staged documents are built in-memory.
"""
from __future__ import annotations

from brain.graph.export import graph_json
from brain.graph.metrics import linkage_completeness, orphans
from brain.graph.model import build_graph
from brain.graph.resolve import (base_tag, canonical_value, propose_merges,
                                  same_asset, similarity)
from brain.schema import (AI, REGEX, STRUCTURED, Chunk, DocumentRecord, EdgeFact,
                          NodeFact, SourceRef, StagedDoc)


def _src(doc="d", conf=1.0):
    return SourceRef(doc_id=doc, path=f"{doc}.txt")


def _asset(value, props=None, extractor=STRUCTURED, conf=1.0, aliases=None):
    return NodeFact(label="Asset", key="tag", value=value,
                    properties=props or {"tag": value}, source=_src(),
                    confidence=conf, extractor=extractor, aliases=aliases or [])


def _doc(doc_id, doc_type, nodes=None, edges=None, chunks=None):
    return StagedDoc(
        document=DocumentRecord(id=doc_id, doc_type=doc_type, title=doc_id, path=f"{doc_id}.txt"),
        nodes=nodes or [], edges=edges or [], chunks=chunks or [],
    )


# --- merging ---------------------------------------------------------------

def test_asset_merged_across_documents():
    d1 = _doc("reg", "ProjectFile", nodes=[_asset("P-101A", {
        "tag": "P-101A", "name": "Crude Feed Pump A", "asset_class": "Pump"})])
    d2 = _doc("inc", "IncidentReport", nodes=[_asset("P-101A", {"tag": "P-101A"},
                                                     extractor=REGEX, conf=0.9)])
    g = build_graph([d1, d2])
    assert len(g.nodes_by_label("Asset")) == 1
    node = g.nodes[("Asset", "P-101A")]
    assert node.properties["name"] == "Crude Feed Pump A"   # register value kept
    assert len(node.sources) == 2                            # provenance from both


def test_structured_property_beats_ai():
    d1 = _doc("ai", "IncidentReport", nodes=[_asset("V-204", {
        "tag": "V-204", "name": "wrong guess"}, extractor=AI, conf=0.6)])
    d2 = _doc("reg", "ProjectFile", nodes=[_asset("V-204", {
        "tag": "V-204", "name": "Reflux Drum"}, extractor=STRUCTURED, conf=1.0)])
    g = build_graph([d1, d2])
    assert g.nodes[("Asset", "V-204")].properties["name"] == "Reflux Drum"


def test_confidence_rises_with_agreement():
    single = build_graph([_doc("a", "Email", nodes=[_asset("E-301", extractor=REGEX, conf=0.9)])])
    multi = build_graph([
        _doc("a", "Email", nodes=[_asset("E-301", extractor=REGEX, conf=0.9)]),
        _doc("b", "SOP", nodes=[_asset("E-301", extractor=REGEX, conf=0.9)]),
    ])
    assert multi.nodes[("Asset", "E-301")].confidence >= single.nodes[("Asset", "E-301")].confidence


def test_no_over_merge_of_backup_pumps():
    g = build_graph([_doc("reg", "ProjectFile",
                          nodes=[_asset("P-101A"), _asset("P-101B")])])
    assert {"P-101A", "P-101B"} == {n.value for n in g.nodes_by_label("Asset")}


def test_canonicalisation_merges_variants():
    # lowercase tag + case-variant failure mode should each collapse to one node
    d = _doc("inc", "IncidentReport", nodes=[
        _asset("p-101a", extractor=REGEX, conf=0.9),
        _asset("P-101A"),
        NodeFact(label="FailureMode", key="name", value="seal failure",
                 properties={"name": "seal failure"}, source=_src(), confidence=0.7, extractor=AI),
        NodeFact(label="FailureMode", key="name", value="Seal Failure",
                 properties={"name": "Seal Failure"}, source=_src(), confidence=0.7, extractor=AI),
    ])
    g = build_graph([d])
    assert len(g.nodes_by_label("Asset")) == 1
    assert len(g.nodes_by_label("FailureMode")) == 1
    assert "p-101a" in g.nodes[("Asset", "P-101A")].aliases   # original surface kept


def test_edge_endpoints_canonicalised():
    d = _doc("inc", "IncidentReport",
             nodes=[_asset("p-101a", extractor=REGEX, conf=0.9)],
             edges=[EdgeFact(type="ABOUT", from_label="Document", from_value="inc",
                             to_label="Asset", to_value="p-101a", source=_src(),
                             confidence=0.9, extractor=REGEX)])
    g = build_graph([d])
    edge = next(iter(g.edges.values()))
    assert edge.to_value == "P-101A"


# --- resolution primitives -------------------------------------------------

def test_resolve_primitives():
    assert same_asset("p-101a", "P-101A") is True
    assert same_asset("P-101A", "P-101B") is False
    assert base_tag("P-101A") == base_tag("P-101B") == "P-101"
    assert canonical_value("Regulation", "OISD STD 105") == "OISD-STD-105"
    assert similarity("Reflux Drum", "Reflux Drum") == 1.0


def test_propose_merges_skips_ab_suffix():
    # A/B backups must NOT be proposed; a genuine near-duplicate should be.
    assert propose_merges("Asset", ["P-101A", "P-101B"]) == []
    props = propose_merges("Person", ["R. Kumar", "R Kumar"], threshold=0.8)
    assert props and props[0][:2] == ("R Kumar", "R. Kumar")


# --- metrics & export ------------------------------------------------------

def test_linkage_and_orphans():
    d = _doc("reg", "ProjectFile", nodes=[_asset("P-101A")],
             edges=[
                 EdgeFact(type="ABOUT", from_label="Document", from_value="reg",
                          to_label="Asset", to_value="P-101A", source=_src(),
                          confidence=1.0, extractor=STRUCTURED),
                 EdgeFact(type="INSPECTS", from_label="Inspection", from_value="I1",
                          to_label="Asset", to_value="P-101A", source=_src(),
                          confidence=1.0, extractor=STRUCTURED),
             ])
    g = build_graph([d])
    link = linkage_completeness(g)
    assert link["assets"] == 1
    assert link["coverage_pct"]["documented"] == 100.0
    assert link["coverage_pct"]["inspected"] == 100.0
    assert link["coverage_pct"]["maintained"] == 0.0        # no work order
    # Inspection node I1 has an edge; not an orphan. Unit-less asset is linked.
    assert "Asset:P-101A" not in orphans(g)


def test_export_hides_chunks_and_marks_hub():
    d = _doc("reg", "ProjectFile", nodes=[_asset("P-101A")],
             chunks=[Chunk(id="reg::c0", doc_id="reg", text="hello", ordinal=0)])
    g = build_graph([d])
    js = graph_json(g, include_chunks=False)
    labels = {n["label"] for n in js["nodes"]}
    assert "Chunk" not in labels
    asset_node = next(n for n in js["nodes"] if n["label"] == "Asset")
    assert asset_node["hub"] is True
