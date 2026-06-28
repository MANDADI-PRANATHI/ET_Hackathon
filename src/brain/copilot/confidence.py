"""Confidence is BUILT from several signals, not taken from the LLM's self-report:
  - retrieval : how well the best passage matched the question (meaning-search score)
  - support   : how many sources back the answer (more = steadier)
  - graph     : average confidence of the graph facts used
The breakdown is returned too, so the number is explainable.
"""
from __future__ import annotations

from typing import Any, Dict, List


def compute_confidence(chunks: List[Dict[str, Any]], facts: List[Dict[str, Any]]) -> Dict[str, Any]:
    retrieval = max((float(c.get("score", 0.0)) for c in chunks), default=0.0)
    n_sources = len(chunks) + (1 if facts else 0)
    support = min(1.0, n_sources / 3.0)
    graph = (sum(float(f.get("confidence", 0.8)) for f in facts) / len(facts)) if facts else 0.7

    score = round(min(1.0, 0.5 * retrieval + 0.2 * support + 0.3 * graph), 2)
    label = "High" if score >= 0.75 else "Medium" if score >= 0.5 else "Low"
    return {
        "score": score,
        "label": label,
        "breakdown": {"retrieval": round(retrieval, 2), "support": round(support, 2),
                      "graph": round(graph, 2)},
    }
