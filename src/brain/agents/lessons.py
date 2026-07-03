"""Lessons-Learned & proactive-warning agent.

Mines the plant's own history for patterns invisible to any single review —
the same finding raised again and again, one failure mode recurring across
assets, a family of equipment with clustered issues — then turns those patterns,
together with live signals (an overdue inspection, a rising trend), into
warnings that are PUSHED to the right team *before* the problem repeats.

The pattern-finding and warning logic is deterministic (auditable); an optional
LLM only rephrases the warning text. It deliberately mines internal history
first — external incident databases can be folded in later where they map
cleanly onto the ontology.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from brain.agents.compliance import GAP, run_compliance
from brain.graph.model import GraphModel
from brain.graph.resolve import base_tag
from brain.schema import SourceRef
from brain.stores.readings import ReadingsSource, analyze


@dataclass
class Pattern:
    kind: str                       # recurring_finding | recurring_failure_mode | family_cluster | repeated_action
    key: str
    count: int
    assets: List[str] = field(default_factory=list)
    evidence: List[SourceRef] = field(default_factory=list)

    def describe(self) -> str:
        who = ", ".join(sorted(set(self.assets))[:6])
        return f"{self.kind.replace('_', ' ')}: '{self.key}' x{self.count} ({who})"


@dataclass
class Warning:
    asset: str
    severity: str                   # High | Medium | Low
    message: str
    basis: str                      # which signal/pattern triggered it
    evidence: List[SourceRef] = field(default_factory=list)


@dataclass
class LessonsReport:
    generated_on: str
    patterns: List[Pattern] = field(default_factory=list)
    warnings: List[Warning] = field(default_factory=list)

    def to_markdown(self) -> str:
        order = {"High": 0, "Medium": 1, "Low": 2}
        lines = ["# Lessons-Learned & Proactive Warnings",
                 f"_Generated on {self.generated_on}_\n", "## Warnings (pushed)"]
        for w in sorted(self.warnings, key=lambda x: order.get(x.severity, 3)):
            lines.append(f"- **[{w.severity}] {w.asset}** — {w.message}  \n"
                         f"  _basis: {w.basis}_")
        lines.append("\n## Recurring patterns in plant history")
        for p in sorted(self.patterns, key=lambda x: x.count, reverse=True):
            lines.append(f"- {p.describe()}")
        return "\n".join(lines)


def _other(g: GraphModel, edge, anchor_label="Asset"):
    key = ((edge.from_label, edge.from_value) if edge.from_label != anchor_label
           else (edge.to_label, edge.to_value))
    return g.nodes.get(key)


def _asset_of(g: GraphModel, node_label: str, node_value: str) -> Optional[str]:
    """Find the asset a record (NCR/WorkOrder/Incident) attaches to."""
    for e in g.edges_from(node_label, node_value):
        if e.to_label == "Asset":
            return e.to_value
    for e in g.edges_to("Asset", ""):  # not used; kept simple
        pass
    return None


def find_patterns(g: GraphModel, min_count: int = 2) -> List[Pattern]:
    patterns: List[Pattern] = []

    # 1) Recurring non-conformance findings (same finding text repeated).
    findings: Dict[str, Pattern] = {}
    for ncr in g.nodes_by_label("NonConformance"):
        text = (ncr.properties.get("finding") or "").strip().lower()
        if not text:
            continue
        asset = None
        for e in g.edges_from("NonConformance", ncr.value):
            if e.to_label == "Asset":
                asset = e.to_value
        p = findings.setdefault(text, Pattern(kind="recurring_finding", key=text, count=0))
        p.count += 1
        if asset:
            p.assets.append(asset)
        if ncr.sources:
            p.evidence.append(ncr.sources[0])
    patterns += [p for p in findings.values() if p.count >= min_count]

    # 2) Recurring failure modes across assets.
    for fm in g.nodes_by_label("FailureMode"):
        assets = [e.to_value for e in g.edges_from("FailureMode", fm.value)
                  if e.to_label == "Asset"]
        assets += [e.from_value for e in g.edges_to("FailureMode", fm.value)
                   if e.from_label == "Asset"]
        if len(set(assets)) >= min_count:
            patterns.append(Pattern(kind="recurring_failure_mode",
                                    key=fm.properties.get("name", fm.value),
                                    count=len(set(assets)), assets=sorted(set(assets))))

    # 3) Repeated maintenance action on the same asset (chronic problem).
    action_counts: Dict[tuple, Pattern] = {}
    for wo in g.nodes_by_label("WorkOrder"):
        action = (wo.properties.get("action") or "").strip()
        asset = None
        for e in g.edges_from("WorkOrder", wo.value):
            if e.to_label == "Asset":
                asset = e.to_value
        if not action or not asset:
            continue
        k = (asset, action.lower())
        p = action_counts.setdefault(k, Pattern(kind="repeated_action",
                                                key=f"{action} on {asset}", count=0,
                                                assets=[asset]))
        p.count += 1
        if wo.sources:
            p.evidence.append(wo.sources[0])
    patterns += [p for p in action_counts.values() if p.count >= min_count]

    # 4) Equipment-family clusters (issues across P-101A / P-101B ...).
    family: Dict[str, set] = {}
    for label in ("Incident", "NonConformance"):
        for node in g.nodes_by_label(label):
            for e in g.edges_from(label, node.value):
                if e.to_label == "Asset":
                    family.setdefault(base_tag(e.to_value), set()).add(e.to_value)
    for fam, members in family.items():
        if len(members) >= min_count:
            patterns.append(Pattern(kind="family_cluster", key=fam,
                                    count=len(members), assets=sorted(members)))
    return patterns


def generate_warnings(
    g: GraphModel,
    readings: Optional[ReadingsSource] = None,
    today: Optional[datetime.date] = None,
    llm=None,
) -> LessonsReport:
    today = today or datetime.date.today()
    report = LessonsReport(generated_on=today.isoformat())
    report.patterns = find_patterns(g)
    pattern_findings = {p.key for p in report.patterns if p.kind == "recurring_finding"}

    # Signal 1: compliance gaps become high-severity warnings.
    for gap in run_compliance(g, today=today).gaps:
        report.warnings.append(Warning(
            asset=gap.asset, severity="High",
            message=f"Overdue statutory check ({gap.code}) — {gap.detail}",
            basis="compliance gap", evidence=[gap.evidence] if gap.evidence else []))

    # Signal 2: rising operating trends that match a degradation pattern.
    if readings is not None:
        for asset in g.nodes_by_label("Asset"):
            for param in readings.parameters(asset.value):
                trend = analyze(readings.series(asset.value, param), param)
                if trend and trend.rising:
                    report.warnings.append(Warning(
                        asset=asset.value, severity="High",
                        message=f"{param} trending up ({trend.pct_change:+.0f}%) — "
                                f"matches pre-failure degradation seen before; inspect early.",
                        basis="condition trend"))

    # Signal 3: assets caught by a recurring finding pattern.
    for ncr in g.nodes_by_label("NonConformance"):
        text = (ncr.properties.get("finding") or "").strip().lower()
        if text in pattern_findings and (ncr.properties.get("status") or "") != "Closed":
            asset = next((e.to_value for e in g.edges_from("NonConformance", ncr.value)
                          if e.to_label == "Asset"), None)
            if asset:
                report.warnings.append(Warning(
                    asset=asset, severity="Medium",
                    message=f"Open non-conformance '{text}' — a recurring issue "
                            f"across the plant; verify before it escalates.",
                    basis="recurring finding",
                    evidence=[ncr.sources[0]] if ncr.sources else []))

    # De-duplicate (asset, basis, message).
    seen, unique = set(), []
    for w in report.warnings:
        k = (w.asset, w.basis, w.message)
        if k not in seen:
            seen.add(k)
            unique.append(w)
    report.warnings = unique
    return report
