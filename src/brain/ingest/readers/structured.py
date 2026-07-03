"""Read structured records (CSV) straight into graph facts — no AI involved.

The facts are already sitting in named columns, so reading them is exact and
free. We recognise a table by the columns it has (not its filename), so this
keeps working if files are renamed or arrive from a different CMMS export.

Every fact is stamped extractor="structured", confidence 1.0, with the raw row
kept as the source evidence for citations.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable, Dict, List, Optional

from brain.ingest.patterns import normalize_tag
from brain.schema import STRUCTURED, EdgeFact, NodeFact, SourceRef
from brain.ingest.readers.base import StructuredResult

Row = Dict[str, str]


def _src(doc_id: str, path: str, row: Row) -> SourceRef:
    evidence = "; ".join(f"{k}={v}" for k, v in row.items() if v)
    return SourceRef(doc_id=doc_id, path=path, evidence=evidence[:300])


def _asset_stub(tag: str, src: SourceRef) -> NodeFact:
    """A bare Asset node from a referenced tag — the register fills in the rest."""
    return NodeFact(
        label="Asset", key="tag", value=normalize_tag(tag),
        properties={"tag": normalize_tag(tag)},
        source=src, confidence=1.0, extractor=STRUCTURED,
    )


# --- one handler per recognised table shape -------------------------------

def _asset_register(row: Row, src: SourceRef):
    tag = normalize_tag(row["tag"])
    node = NodeFact(
        label="Asset", key="tag", value=tag,
        properties={
            "tag": tag, "name": row.get("name"), "asset_class": row.get("asset_class"),
            "manufacturer": row.get("manufacturer"), "unit_ref": row.get("unit"),
            "criticality": row.get("criticality"),
        },
        source=src, confidence=1.0, extractor=STRUCTURED,
    )
    edges = []
    if row.get("unit"):
        edges.append(EdgeFact(
            type="LOCATED_IN", from_label="Asset", from_value=tag,
            to_label="Unit", to_value=row["unit"], source=src,
            confidence=1.0, extractor=STRUCTURED,
        ))
    text = (f"Asset {tag} ({row.get('name','')}) is a {row.get('asset_class','')} "
            f"by {row.get('manufacturer','')} in unit {row.get('unit','')}, "
            f"criticality {row.get('criticality','')}.")
    unit_nodes = ([NodeFact(label="Unit", key="name", value=row["unit"],
                            properties={"name": row["unit"]}, source=src,
                            confidence=1.0, extractor=STRUCTURED)]
                  if row.get("unit") else [])
    return [node, *unit_nodes], edges, text


def _work_orders(row: Row, src: SourceRef):
    wo = row["wo_number"]
    tag = normalize_tag(row["asset_tag"])
    node = NodeFact(
        label="WorkOrder", key="wo_number", value=wo,
        properties={"wo_number": wo, "action": row.get("action"),
                    "date": row.get("date"), "status": row.get("status"),
                    "performed_by": row.get("performed_by")},
        source=src, confidence=1.0, extractor=STRUCTURED,
    )
    edges = [EdgeFact(type="MAINTAINS", from_label="WorkOrder", from_value=wo,
                      to_label="Asset", to_value=tag, source=src,
                      confidence=1.0, extractor=STRUCTURED)]
    nodes = [node, _asset_stub(tag, src)]
    if row.get("performed_by"):
        who = row["performed_by"]
        nodes.append(NodeFact(label="Person", key="id", value=who,
                              properties={"id": who, "name": who}, source=src,
                              confidence=1.0, extractor=STRUCTURED, needs_review=False))
        edges.append(EdgeFact(type="PERFORMED", from_label="Person", from_value=who,
                              to_label="WorkOrder", to_value=wo, source=src,
                              confidence=1.0, extractor=STRUCTURED))
    text = (f"Work order {wo} on asset {tag}: {row.get('action','')} "
            f"({row.get('status','')}) dated {row.get('date','')}, "
            f"performed by {row.get('performed_by','')}.")
    return nodes, edges, text


def _inspections(row: Row, src: SourceRef):
    iid = row["inspection_id"]
    tag = normalize_tag(row["asset_tag"])
    node = NodeFact(
        label="Inspection", key="inspection_id", value=iid,
        properties={"inspection_id": iid, "type": row.get("type"),
                    "last_inspection_date": row.get("last_inspection_date"),
                    "result": row.get("result")},
        source=src, confidence=1.0, extractor=STRUCTURED,
    )
    edges = [EdgeFact(type="INSPECTS", from_label="Inspection", from_value=iid,
                      to_label="Asset", to_value=tag, source=src,
                      confidence=1.0, extractor=STRUCTURED)]
    text = (f"Inspection {iid} ({row.get('type','')}) on asset {tag}: "
            f"result {row.get('result','')}, last done {row.get('last_inspection_date','')}.")
    return [node, _asset_stub(tag, src)], edges, text


def _permits(row: Row, src: SourceRef):
    pno = row["permit_no"]
    tag = normalize_tag(row["asset_tag"])
    node = NodeFact(
        label="Permit", key="permit_no", value=pno,
        properties={"permit_no": pno, "work_type": row.get("work_type"),
                    "issue_date": row.get("issue_date"), "status": row.get("status")},
        source=src, confidence=1.0, extractor=STRUCTURED,
    )
    edges = [EdgeFact(type="FOR_WORK_ON", from_label="Permit", from_value=pno,
                      to_label="Asset", to_value=tag, source=src,
                      confidence=1.0, extractor=STRUCTURED)]
    text = (f"Permit {pno} ({row.get('work_type','')}) for work on asset {tag}: "
            f"status {row.get('status','')}, issued {row.get('issue_date','')}.")
    return [node, _asset_stub(tag, src)], edges, text


def _nonconformances(row: Row, src: SourceRef):
    ncr = row["ncr_id"]
    tag = normalize_tag(row["asset_tag"])
    nodes = [
        NodeFact(label="NonConformance", key="id", value=ncr,
                 properties={"id": ncr, "finding": row.get("finding"),
                             "raised_date": row.get("raised_date"),
                             "status": row.get("status")},
                 source=src, confidence=1.0, extractor=STRUCTURED),
        _asset_stub(tag, src),
    ]
    edges = [EdgeFact(type="RAISED_AGAINST", from_label="NonConformance", from_value=ncr,
                      to_label="Asset", to_value=tag, source=src,
                      confidence=1.0, extractor=STRUCTURED)]
    if row.get("capa_id"):
        capa = row["capa_id"]
        nodes.append(NodeFact(label="CAPA", key="id", value=capa,
                              properties={"id": capa, "status": row.get("status")},
                              source=src, confidence=1.0, extractor=STRUCTURED))
        edges.append(EdgeFact(type="ADDRESSES", from_label="CAPA", from_value=capa,
                              to_label="NonConformance", to_value=ncr, source=src,
                              confidence=1.0, extractor=STRUCTURED))
    text = (f"Non-conformance {ncr} raised against asset {tag}: "
            f"{row.get('finding','')} ({row.get('status','')}), "
            f"raised {row.get('raised_date','')}, addressed by {row.get('capa_id','')}.")
    return nodes, edges, text


# Recognise a table by a set of columns it must contain.
Handler = Callable[[Row, SourceRef], tuple]
RECOGNIZERS: List[tuple[frozenset, Handler]] = [
    (frozenset({"tag", "asset_class"}), _asset_register),
    (frozenset({"wo_number", "asset_tag"}), _work_orders),
    (frozenset({"inspection_id", "asset_tag"}), _inspections),
    (frozenset({"permit_no", "asset_tag"}), _permits),
    (frozenset({"ncr_id", "asset_tag"}), _nonconformances),
]


def is_structured(path: Path) -> bool:
    return path.suffix.lower() in {".csv", ".tsv"}


def _match_handler(columns: set) -> Optional[Handler]:
    for required, handler in RECOGNIZERS:
        if required <= columns:
            return handler
    return None


def read_structured(path: Path, doc_id: str) -> StructuredResult:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        rows = list(reader)
        columns = set(reader.fieldnames or [])

    result = StructuredResult()
    handler = _match_handler(columns)
    if handler is None:
        # Unknown table: still make it searchable, just don't invent graph facts.
        for row in rows:
            result.row_texts.append("; ".join(f"{k}: {v}" for k, v in row.items() if v))
        return result

    for row in rows:
        src = _src(doc_id, str(path), row)
        nodes, edges, text = handler(row, src)
        result.nodes.extend(nodes)
        result.edges.extend(edges)
        result.row_texts.append(text)
    return result
