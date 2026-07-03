"""Level 4c regression tests — lessons-learned patterns + proactive warnings."""
from __future__ import annotations

import datetime

from brain.agents.lessons import find_patterns, generate_warnings
from brain.graph.model import GraphModel
from brain.schema import STRUCTURED, SourceRef
from brain.stores.readings import ReadingPoint

TODAY = datetime.date(2026, 7, 3)
SRC = SourceRef(doc_id="d", path="d.csv")


def _ncr(g, ncr_id, asset, finding, status="Open"):
    g.add_node("NonConformance", "id", ncr_id,
               {"id": ncr_id, "finding": finding, "status": status}, SRC, 1.0, STRUCTURED)
    g.add_node("Asset", "tag", asset, {"tag": asset, "asset_class": "Valve"}, SRC, 1.0, STRUCTURED)
    g.add_edge("RAISED_AGAINST", "NonConformance", ncr_id, "Asset", asset, SRC, 1.0, STRUCTURED)


def test_recurring_finding_pattern():
    g = GraphModel()
    _ncr(g, "NCR-1", "PSV-110A", "Inspection overdue")
    _ncr(g, "NCR-2", "FT-150", "Inspection overdue")
    _ncr(g, "NCR-3", "E-301", "Missing record")
    pats = find_patterns(g)
    rec = [p for p in pats if p.kind == "recurring_finding"]
    assert any(p.key == "inspection overdue" and p.count == 2 for p in rec)


def test_family_cluster_pattern():
    g = GraphModel()
    _ncr(g, "NCR-1", "P-101A", "Seal leak")
    _ncr(g, "NCR-2", "P-101B", "Seal leak")
    pats = find_patterns(g)
    fam = [p for p in pats if p.kind == "family_cluster"]
    assert any(p.key == "P-101" and set(p.assets) == {"P-101A", "P-101B"} for p in fam)


def test_repeated_action_pattern():
    g = GraphModel()
    g.add_node("Asset", "tag", "C-102", {"tag": "C-102", "asset_class": "Compressor"},
               SRC, 1.0, STRUCTURED)
    for i in (1, 2):
        g.add_node("WorkOrder", "wo_number", f"WO-{i}",
                   {"wo_number": f"WO-{i}", "action": "Seal replacement"}, SRC, 1.0, STRUCTURED)
        g.add_edge("MAINTAINS", "WorkOrder", f"WO-{i}", "Asset", "C-102", SRC, 1.0, STRUCTURED)
    pats = find_patterns(g)
    assert any(p.kind == "repeated_action" and p.count == 2 for p in pats)


def test_compliance_gap_becomes_warning():
    g = GraphModel()
    g.add_node("Asset", "tag", "PSV-1", {"tag": "PSV-1", "asset_class": "Valve"},
               SRC, 1.0, STRUCTURED)
    g.add_node("Inspection", "inspection_id", "I1",
               {"inspection_id": "I1", "last_inspection_date": "2025-11-06"}, SRC, 1.0, STRUCTURED)
    g.add_edge("INSPECTS", "Inspection", "I1", "Asset", "PSV-1", SRC, 1.0, STRUCTURED)
    report = generate_warnings(g, today=TODAY)
    gap_warnings = [w for w in report.warnings if w.basis == "compliance gap"]
    assert gap_warnings and gap_warnings[0].asset == "PSV-1" and gap_warnings[0].severity == "High"


class _RisingReadings:
    def parameters(self, asset):
        return ["vibration"] if asset == "P-1" else []

    def series(self, asset, parameter, since=None):
        base = datetime.date(2026, 3, 1)
        return [ReadingPoint(base + datetime.timedelta(weeks=i), v, "mm/s")
                for i, v in enumerate([2.4, 3.8, 5.5, 7.0])]


def test_condition_trend_becomes_warning():
    g = GraphModel()
    g.add_node("Asset", "tag", "P-1", {"tag": "P-1", "asset_class": "Pump"},
               SRC, 1.0, STRUCTURED)
    report = generate_warnings(g, readings=_RisingReadings(), today=TODAY)
    trend_warnings = [w for w in report.warnings if w.basis == "condition trend"]
    assert trend_warnings and trend_warnings[0].asset == "P-1"
