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
