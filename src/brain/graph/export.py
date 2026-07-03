"""Export the merged graph as plain JSON for visualisation (the demo money-shot).

Chunk nodes and their embeddings are dropped by default so the picture shows the
asset-centric structure a human cares about — assets at the hub, with documents,
work orders, inspections, incidents and regulations hanging off them.
"""
from __future__ import annotations

from typing import Any, Dict

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


def asset_list(g: GraphModel) -> Dict[str, Any]:
    """Lightweight list of assets (for the graph-tab picker)."""
    assets = sorted(g.nodes_by_label("Asset"), key=lambda n: n.value)
    return {"assets": [{"value": n.value,
                        "display": n.properties.get("name") or n.value}
                       for n in assets]}
