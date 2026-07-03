"""Level 4b regression tests — readings adapter + RCA agent.

The signal detection (trend, schedule) is deterministic code, so it is pinned
exactly. Narrative uses a stub / template.
"""
from __future__ import annotations

import datetime

from brain.agents.rca import investigate
from brain.graph.model import GraphModel
from brain.schema import STRUCTURED, SourceRef
from brain.stores.readings import FileReadingsSource, ReadingPoint, analyze

TODAY = datetime.date(2026, 5, 20)
SRC = SourceRef(doc_id="d", path="d.csv")


def _pts(values, start=datetime.date(2026, 3, 1)):
    return [ReadingPoint(start + datetime.timedelta(weeks=i), v, "mm/s")
            for i, v in enumerate(values)]


def test_analyze_detects_rising_and_flat():
    rising = analyze(_pts([2.4, 3.5, 5.0, 7.2]), "vibration")
    assert rising.rising and rising.pct_change > 25
    assert rising.peak == 7.2
    flat = analyze(_pts([2.4, 2.5, 2.4, 2.45]), "vibration")
    assert not flat.rising


def test_file_readings_source(tmp_path):
    p = tmp_path / "r.csv"
    p.write_text("asset_tag,parameter,timestamp,value,unit\n"
                 "P-1,vibration,2026-03-01,2.4,mm/s\n"
                 "P-1,vibration,2026-03-08,5.0,mm/s\n", encoding="utf-8")
    src = FileReadingsSource(p)
    assert src.parameters("P-1") == ["vibration"]
    series = src.series("P-1", "vibration")
    assert [r.value for r in series] == [2.4, 5.0]      # sorted by date


def _asset_graph():
    g = GraphModel()
    g.add_node("Asset", "tag", "P-1",
               {"tag": "P-1", "asset_class": "Pump", "criticality": "High"},
               SRC, 1.0, STRUCTURED)
    g.add_node("Inspection", "inspection_id", "I1",
               {"inspection_id": "I1", "last_inspection_date": "2026-01-10"},
               SRC, 1.0, STRUCTURED)
    g.add_edge("INSPECTS", "Inspection", "I1", "Asset", "P-1", SRC, 1.0, STRUCTURED)
    return g


class _RisingReadings:
    def parameters(self, asset):
        return ["vibration"]

    def series(self, asset, parameter, since=None):
        return _pts([2.4, 3.6, 5.1, 7.2])


def test_investigate_surfaces_condition_and_recommendation():
    g = _asset_graph()
    report = investigate(g, "P-1", readings=_RisingReadings(), today=TODAY)
    assert report.findings
    top = report.findings[0]
    assert top.kind == "condition" and "vibration" in top.cause
    assert report.recommendations and report.recommendations[0].urgency == "High"
    assert report.trends and report.trends[0].rising
    # schedule includes a preventive-maintenance entry
    assert any("Preventive" in s["task"] for s in report.schedule)


def test_investigate_without_readings_is_safe():
    g = _asset_graph()
    report = investigate(g, "P-1", readings=None, today=TODAY)
    assert report.asset == "P-1"
    assert isinstance(report.narrative, str) and report.narrative
