"""Graph quality metrics — knowledge-graph linkage completeness (a judged metric).

Because the graph is asset-centric, "completeness" means: is each asset actually
connected to the knowledge that should surround it — the documents that describe
it, the maintenance done on it, the inspections that cover it? We report coverage
per dimension and flag orphans (nodes connected to nothing), so gaps are visible
rather than hidden.
"""
from __future__ import annotations

from typing import Dict, List

from brain.graph.model import GraphModel

# relationship types that connect *to* an Asset, grouped by knowledge dimension
_ASSET_DIMENSIONS = {
    "documented": {"ABOUT", "MENTIONS"},
    "maintained": {"MAINTAINS"},
    "inspected": {"INSPECTS"},
}


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def linkage_completeness(g: GraphModel) -> Dict[str, object]:
    assets = g.nodes_by_label("Asset")
    n = len(assets)
    covered = {dim: 0 for dim in _ASSET_DIMENSIONS}
    per_asset: List[dict] = []

    for a in assets:
        incident = g.neighbours("Asset", a.value)
        rel_types = {e.type for e in incident}
        dims = {dim: bool(rels & rel_types) for dim, rels in _ASSET_DIMENSIONS.items()}
        for dim, ok in dims.items():
            covered[dim] += int(ok)
        per_asset.append({"asset": a.value, "relationships": len(incident), **dims})

    coverage = {dim: _pct(covered[dim], n) for dim in _ASSET_DIMENSIONS}
    linkage_score = round(sum(coverage.values()) / (100.0 * len(coverage)), 3) if n else 0.0
    return {
        "assets": n,
        "coverage_pct": coverage,
        "linkage_score": linkage_score,   # 0..1, mean coverage across dimensions
        "per_asset": per_asset,
    }


def orphans(g: GraphModel) -> List[str]:
    """Nodes connected to nothing (excluding Chunks, which link via PART_OF)."""
    out = []
    for (label, value), node in g.nodes.items():
        if label in ("Chunk",):
            continue
        if not g.neighbours(label, value):
            out.append(f"{label}:{value}")
    return out


def graph_stats(g: GraphModel) -> Dict[str, object]:
    by_label: Dict[str, int] = {}
    for (label, _v) in g.nodes:
        by_label[label] = by_label.get(label, 0) + 1
    by_type: Dict[str, int] = {}
    for e in g.edges.values():
        by_type[e.type] = by_type.get(e.type, 0) + 1

    review_nodes = sum(1 for n in g.nodes.values() if n.needs_review)
    review_edges = sum(1 for e in g.edges.values() if e.needs_review)
    return {
        "nodes_total": len(g.nodes),
        "edges_total": len(g.edges),
        "nodes_by_label": dict(sorted(by_label.items())),
        "edges_by_type": dict(sorted(by_type.items())),
        "needs_review": {"nodes": review_nodes, "edges": review_edges},
        "linkage": linkage_completeness(g),
        "orphans": orphans(g),
    }
