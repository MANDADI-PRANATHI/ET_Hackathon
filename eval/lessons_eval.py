"""Lessons-learned quality check — does the agent surface known patterns and
push the right warnings? Self-contained deterministic scenario.

  python eval/lessons_eval.py [--json]
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from brain.agents.lessons import find_patterns, generate_warnings  # noqa: E402
from brain.graph.model import GraphModel                           # noqa: E402
from brain.schema import STRUCTURED, SourceRef                     # noqa: E402
from brain.stores.readings import ReadingPoint                     # noqa: E402

TODAY = datetime.date(2026, 7, 3)
SRC = SourceRef(doc_id="scenario", path="scenario")


class _Readings:
    def parameters(self, asset):
        return ["vibration"] if asset == "P-101A" else []

    def series(self, asset, parameter, since=None):
        base = datetime.date(2026, 3, 1)
        return [ReadingPoint(base + datetime.timedelta(weeks=i), v, "mm/s")
                for i, v in enumerate([2.4, 3.5, 5.0, 7.2])]


def _scenario() -> GraphModel:
    g = GraphModel()
    # Two pumps in a family, each with the same recurring finding.
    for tag in ("P-101A", "P-101B"):
        g.add_node("Asset", "tag", tag, {"tag": tag, "asset_class": "Pump"}, SRC, 1.0, STRUCTURED)
    for i, tag in enumerate(("P-101A", "P-101B"), 1):
        nid = f"NCR-{i}"
        g.add_node("NonConformance", "id", nid,
                   {"id": nid, "finding": "Seal leak", "status": "Open"}, SRC, 1.0, STRUCTURED)
        g.add_edge("RAISED_AGAINST", "NonConformance", nid, "Asset", tag, SRC, 1.0, STRUCTURED)
    # An overdue valve (compliance gap).
    g.add_node("Asset", "tag", "PSV-110B", {"tag": "PSV-110B", "asset_class": "Valve"},
               SRC, 1.0, STRUCTURED)
    g.add_node("Inspection", "inspection_id", "I1",
               {"inspection_id": "I1", "last_inspection_date": "2025-11-06"}, SRC, 1.0, STRUCTURED)
    g.add_edge("INSPECTS", "Inspection", "I1", "Asset", "PSV-110B", SRC, 1.0, STRUCTURED)
    return g


def evaluate() -> dict:
    g = _scenario()
    report = generate_warnings(g, readings=_Readings(), today=TODAY)
    kinds = {p.kind for p in report.patterns}
    bases = {w.basis for w in report.warnings}
    checks = {
        "recurring_finding_pattern": "recurring_finding" in kinds,
        "family_cluster_pattern": "family_cluster" in kinds,
        "compliance_gap_warning": "compliance gap" in bases,
        "condition_trend_warning": "condition trend" in bases,
        "recurring_finding_warning": "recurring finding" in bases,
    }
    return {"checks": checks, "score": round(sum(checks.values()) / len(checks), 3),
            "warnings": len(report.warnings), "patterns": len(report.patterns)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = evaluate()
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print("Lessons-learned quality check\n")
    for k, v in result["checks"].items():
        print(f"  [{'ok' if v else 'XX'}] {k}")
    print(f"\n  score: {result['score']}  "
          f"({result['warnings']} warnings, {result['patterns']} patterns)")


if __name__ == "__main__":
    main()
