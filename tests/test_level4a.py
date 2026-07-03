"""Level 4a regression tests — the compliance rule engine.

The pass/fail decision is made by plain code (deterministic dates), so these
tests pin the exact behaviour. The LLM clause parser is tested with a stub.
"""
from __future__ import annotations

import datetime

from brain.agents.compliance import (GAP, MET, UNKNOWN, RegRequirement,
                                      check_requirement, parse_clause, run_compliance)
from brain.graph.model import GraphModel
from brain.schema import STRUCTURED, SourceRef

TODAY = datetime.date(2026, 7, 3)
SRC = SourceRef(doc_id="d", path="d.csv")
VALVE_RULE = RegRequirement(id="R", code="OISD-STD-105", clause="6 months",
                            applies_to_class="Valve", check_type="interval_days",
                            interval_days=182)


def _graph_with_valve(last_date):
    g = GraphModel()
    g.add_node("Asset", "tag", "PSV-1", {"tag": "PSV-1", "asset_class": "Valve"},
               SRC, 1.0, STRUCTURED)
    if last_date is not None:
        g.add_node("Inspection", "inspection_id", "I1",
                   {"inspection_id": "I1", "last_inspection_date": last_date},
                   SRC, 1.0, STRUCTURED)
        g.add_edge("INSPECTS", "Inspection", "I1", "Asset", "PSV-1", SRC, 1.0, STRUCTURED)
    return g


def test_overdue_is_gap():
    g = _graph_with_valve("2025-11-06")            # 239 days before TODAY
    [res] = check_requirement(g, VALVE_RULE, TODAY)
    assert res.status == GAP
    assert res.days_since == 239
    assert "exceeds" in res.detail
    assert res.evidence is not None


def test_recent_is_met():
    g = _graph_with_valve("2026-05-01")            # 63 days
    [res] = check_requirement(g, VALVE_RULE, TODAY)
    assert res.status == MET


def test_missing_inspection_is_unknown():
    g = _graph_with_valve(None)
    [res] = check_requirement(g, VALVE_RULE, TODAY)
    assert res.status == UNKNOWN


def test_rule_only_applies_to_its_class():
    g = GraphModel()
    g.add_node("Asset", "tag", "P-1", {"tag": "P-1", "asset_class": "Pump"},
               SRC, 1.0, STRUCTURED)
    assert check_requirement(g, VALVE_RULE, TODAY) == []   # pump ignored by valve rule


def test_report_summary_and_drafts():
    g = _graph_with_valve("2025-11-06")
    report = run_compliance(g, ruleset=[VALVE_RULE], today=TODAY)
    assert report.summary[GAP] == 1
    md = report.to_markdown()
    assert "GAP" in md and "PSV-1" in md
    drafts = report.drafts()
    assert len(drafts) == 1
    assert drafts[0]["non_conformance"]["asset"] == "PSV-1"
    assert drafts[0]["capa"]["id"].startswith("CAPA-AUTO")


class _StubLLM:
    def __init__(self, reply):
        self.reply = reply

    def generate(self, prompt, system=None):
        return self.reply


def test_parse_clause_authoring():
    reply = '[{"applies_to_class":"Valve","check_type":"interval_days","interval_days":182,"description":"6-month valve check"}]'
    reqs = parse_clause("valves every six months", "OISD-STD-105", _StubLLM(reply))
    assert len(reqs) == 1
    assert reqs[0].applies_to_class == "Valve" and reqs[0].interval_days == 182
    # no LLM -> no rules (curated RULESET is used elsewhere)
    assert parse_clause("text", "X", None) == []
    assert parse_clause("text", "X", _StubLLM("not json")) == []
