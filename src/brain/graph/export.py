"""Export the merged graph as plain JSON for visualisation (the demo money-shot).

Chunk nodes and their embeddings are dropped by default so the picture shows the
asset-centric structure a human cares about — assets at the hub, with documents,
work orders, inspections, incidents and regulations hanging off them.

Also builds the per-asset TIMELINE ("digital-twin history"): every dated record
connected to an asset — work orders, inspections, incidents, non-conformances,
permits, CAPAs — merged into one chronological story. Pure code over facts the
graph already holds; no model call.
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from brain.graph.model import GraphModel

_HIDDEN_WITH_CHUNKS = {"Chunk"}
_HIDDEN_EDGES_WITH_CHUNKS = {"PART_OF", "MENTIONS"}


def graph_json(g: GraphModel, include_chunks: bool = False) -> Dict[str, Any]:
    nodes = []
    for (label, value), n in g.nodes.items():
        if not include_chunks and label in _HIDDEN_WITH_CHUNKS:
            continue
        props = {k: v for k, v in n.properties.items() if k != "embedding"}
        nodes.append({
            "id": f"{label}:{value}",
            "label": label,
            "value": value,
            "display": n.properties.get("name") or n.properties.get("title") or value,
            "confidence": n.confidence,
            "needs_review": n.needs_review,
            "hub": label == "Asset",
            "properties": props,
        })
    present = {n["id"] for n in nodes}

    edges = []
    for e in g.edges.values():
        if not include_chunks and (
            e.type in _HIDDEN_EDGES_WITH_CHUNKS
            or e.from_label in _HIDDEN_WITH_CHUNKS
            or e.to_label in _HIDDEN_WITH_CHUNKS
        ):
            continue
        src, dst = f"{e.from_label}:{e.from_value}", f"{e.to_label}:{e.to_value}"
        if src in present and dst in present:
            edges.append({"source": src, "target": dst, "type": e.type,
                          "confidence": e.confidence})
    return {"nodes": nodes, "edges": edges}


def asset_subgraph(g: GraphModel, asset_value: str, limit: int = 28) -> Dict[str, Any]:
    """The neighbourhood of one asset (hub + its connected records), capped for a
    readable visualisation — scales to a huge graph because we never ship it all."""
    hub_key = ("Asset", asset_value)
    if hub_key not in g.nodes:
        return {"nodes": [], "edges": [], "total_connections": 0, "shown": 0}

    rel_edges = [e for e in g.neighbours("Asset", asset_value)
                 if e.type not in ("MENTIONS", "PART_OF")
                 and "Chunk" not in (e.from_label, e.to_label)]
    total = len(rel_edges)
    # Prefer the most confident / diverse connections when capping.
    rel_edges = sorted(rel_edges, key=lambda e: e.confidence, reverse=True)[:limit]

    node_keys = {hub_key}
    for e in rel_edges:
        other = ((e.from_label, e.from_value) if e.from_label != "Asset"
                 else (e.to_label, e.to_value))
        node_keys.add(other)

    nodes = []
    for label, value in node_keys:
        n = g.nodes.get((label, value))
        if not n:
            continue
        nodes.append({
            "id": f"{label}:{value}", "label": label, "value": value,
            "display": n.properties.get("name") or n.properties.get("title") or value,
            "hub": label == "Asset" and value == asset_value,
        })
    present = {n["id"] for n in nodes}
    edges = [{"source": f"{e.from_label}:{e.from_value}",
              "target": f"{e.to_label}:{e.to_value}", "type": e.type}
             for e in rel_edges
             if f"{e.from_label}:{e.from_value}" in present
             and f"{e.to_label}:{e.to_value}" in present]
    return {"nodes": nodes, "edges": edges, "total_connections": total, "shown": len(edges)}


# Which property holds the event date, per record type, and how to describe it.
_TIMELINE_LABELS = {
    "WorkOrder":      ("date",                 "action"),
    "Inspection":     ("last_inspection_date", "type"),
    "Incident":       ("date",                 "title"),
    "NonConformance": ("raised_date",          "finding"),
    "Permit":         ("issue_date",           "work_type"),
    "CAPA":           ("due_date",             "action"),
}


def _event_date(s: Optional[str]) -> Optional[str]:
    """Normalise a date string to ISO (YYYY-MM-DD) or None if unparseable."""
    if not s:
        return None
    s = str(s).strip()
    try:
        return datetime.date.fromisoformat(s[:10]).isoformat()
    except ValueError:
        pass
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def asset_timeline(g: GraphModel, asset_value: str) -> Dict[str, Any]:
    """One asset's whole documented life in date order — every connected work
    order, inspection, incident, NCR, permit and CAPA, each with its source."""
    if ("Asset", asset_value) not in g.nodes:
        return {"asset": asset_value, "events": [], "undated": 0}

    events: List[Dict[str, Any]] = []
    undated = 0
    for e in g.neighbours("Asset", asset_value):
        other_key = ((e.from_label, e.from_value) if e.from_label != "Asset"
                     else (e.to_label, e.to_value))
        node = g.nodes.get(other_key)
        if node is None or node.label not in _TIMELINE_LABELS:
            continue
        date_prop, detail_prop = _TIMELINE_LABELS[node.label]
        date = _event_date(node.properties.get(date_prop))
        if date is None:
            undated += 1
            continue
        src = node.sources[0] if node.sources else None
        events.append({
            "date": date,
            "kind": node.label,
            "id": node.value,
            "detail": node.properties.get(detail_prop) or "",
            "status": node.properties.get("status") or node.properties.get("result") or "",
            "source": src.path if src else None,
            "confidence": node.confidence,
        })
    # One record can reach the asset over several edges — keep each event once.
    seen: set = set()
    unique = []
    for ev in sorted(events, key=lambda x: (x["date"], x["kind"], x["id"])):
        k = (ev["kind"], ev["id"])
        if k not in seen:
            seen.add(k)
            unique.append(ev)
    return {"asset": asset_value, "events": unique, "undated": undated}


def asset_list(g: GraphModel) -> Dict[str, Any]:
    """Lightweight list of assets (for the graph-tab picker)."""
    assets = sorted(g.nodes_by_label("Asset"), key=lambda n: n.value)
    return {"assets": [{"value": n.value,
                        "display": n.properties.get("name") or n.value}
                       for n in assets]}
