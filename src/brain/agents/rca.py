"""Maintenance & RCA agent — connect the dots no one person can.

For an asset it fuses what usually lives apart: work-order history, inspection
findings, linked failure modes and incidents (from the graph), AND recent
operating readings (from the readings adapter). The *signals* are computed by
code — a rising vibration trend, a maintenance action just before a trip, an
overdue inspection — so the root-cause reasoning is grounded, not guessed. An
optional LLM writes the narrative on top; without one, a templated summary is
produced from the same findings.

Outputs: ranked root-cause findings (each cited), a predictive recommendation,
and an optimised maintenance schedule.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import List, Optional

from brain.agents.compliance import RULESET
from brain.graph.model import GraphModel
from brain.schema import SourceRef
from brain.stores.readings import ReadingsSource, TrendAnalysis, analyze

# preventive-maintenance cadence by criticality (days)
_PM_DAYS = {"High": 90, "Medium": 180, "Low": 365}
_INTERVAL_BY_CLASS = {r.applies_to_class: r.interval_days
                      for r in RULESET if r.interval_days}


@dataclass
class Finding:
    cause: str
    rationale: str
    confidence: float
    kind: str                       # condition | failure_mode | maintenance | inspection
    evidence: List[SourceRef] = field(default_factory=list)


@dataclass
class Recommendation:
    action: str
    urgency: str                    # High | Medium | Low
    rationale: str
    due_date: Optional[str] = None


@dataclass
class RCAReport:
    asset: str
    assessed_on: str
    findings: List[Finding] = field(default_factory=list)
    trends: List[TrendAnalysis] = field(default_factory=list)
    recommendations: List[Recommendation] = field(default_factory=list)
    schedule: List[dict] = field(default_factory=list)
    narrative: str = ""

    def to_markdown(self) -> str:
        lines = [f"# RCA & Maintenance Report — {self.asset}",
                 f"_Assessed on {self.assessed_on}_\n"]
        if self.narrative:
            lines += [self.narrative, ""]
        lines.append("## Root-cause findings (ranked)")
        for i, f in enumerate(self.findings, 1):
            lines.append(f"{i}. **{f.cause}** ({f.kind}, confidence {f.confidence:.2f})  \n"
                         f"   {f.rationale}")
        if self.trends:
            lines.append("\n## Operating conditions")
            for t in self.trends:
                lines.append(f"- {t.describe()}")
        if self.recommendations:
            lines.append("\n## Recommendations")
            for r in self.recommendations:
                due = f" (by {r.due_date})" if r.due_date else ""
                lines.append(f"- [{r.urgency}] {r.action}{due} — {r.rationale}")
        if self.schedule:
            lines.append("\n## Optimised schedule")
            for s in self.schedule:
                lines.append(f"- {s['task']}: {s['due_date']} ({s['basis']})")
        return "\n".join(lines)


def _parse_date(s) -> Optional[datetime.date]:
    try:
        return datetime.date.fromisoformat(str(s).strip()[:10])
    except (ValueError, AttributeError):
        return None


def _edge_source(edge) -> Optional[SourceRef]:
    return edge.sources[0] if edge.sources else None


def _collect(g: GraphModel, asset: str):
    """Gather the asset's maintenance-relevant neighbours from the graph."""
    work_orders, inspections, failure_modes, incidents = [], [], [], []
    for e in g.neighbours("Asset", asset):
        other_key = ((e.from_label, e.from_value) if (e.from_label != "Asset")
                     else (e.to_label, e.to_value))
        other = g.nodes.get(other_key)
        if other is None:
            continue
        if e.type == "MAINTAINS":
            work_orders.append((other, e))
        elif e.type == "INSPECTS":
            inspections.append((other, e))
        elif e.type == "AFFECTS":
            failure_modes.append((other, e))
        elif e.type == "INVOLVES":
            incidents.append((other, e))
    return work_orders, inspections, failure_modes, incidents


def investigate(
    g: GraphModel,
    asset: str,
    readings: Optional[ReadingsSource] = None,
    today: Optional[datetime.date] = None,
    llm=None,
) -> RCAReport:
    today = today or datetime.date.today()
    report = RCAReport(asset=asset, assessed_on=today.isoformat())
    work_orders, inspections, failure_modes, incidents = _collect(g, asset)

    # 1) Operating-condition signal (readings) — deterministic trend detection.
    if readings is not None:
        for param in readings.parameters(asset):
            trend = analyze(readings.series(asset, param), param)
            if trend is None:
                continue
            report.trends.append(trend)
            if trend.rising:
                report.findings.append(Finding(
                    cause=f"Degradation trend in {param}",
                    rationale=f"Readings show {trend.describe()} — consistent with "
                              f"developing mechanical wear before failure.",
                    confidence=0.8, kind="condition",
                    evidence=[SourceRef(doc_id="readings", path="readings adapter",
                                        evidence=trend.describe())]))

    # 2) Known failure modes linked in the graph.
    for fm, e in failure_modes:
        report.findings.append(Finding(
            cause=fm.properties.get("name", fm.value),
            rationale="Failure mode linked to this asset in incident/maintenance records.",
            confidence=e.confidence, kind="failure_mode",
            evidence=[s for s in [_edge_source(e)] if s]))

    # 3) Recent maintenance that could have induced the failure.
    recent = sorted(
        [(wo, e) for wo, e in work_orders if _parse_date(wo.properties.get("date"))],
        key=lambda x: _parse_date(x[0].properties.get("date")), reverse=True)
    for wo, e in recent[:3]:
        d = _parse_date(wo.properties.get("date"))
        age = (today - d).days if d else None
        if age is not None and age <= 45:
            report.findings.append(Finding(
                cause=f"Recent maintenance: {wo.properties.get('action')}",
                rationale=f"Work order {wo.properties.get('wo_number')} was {age} days "
                          f"ago — recent intervention can introduce faults "
                          f"(e.g. misalignment after seal work).",
                confidence=0.55, kind="maintenance",
                evidence=[s for s in [_edge_source(e)] if s]))

    report.findings.sort(key=lambda f: f.confidence, reverse=True)

    # Recommendations from the strongest condition signal.
    rising = [t for t in report.trends if t.rising]
    if rising:
        t = max(rising, key=lambda x: x.pct_change)
        report.recommendations.append(Recommendation(
            action=f"Inspect bearing/seal and verify alignment on {asset}",
            urgency="High",
            rationale=f"{t.parameter} up {t.pct_change:+.0f}% (peak {t.peak:g}{t.unit}); "
                      f"act before it reaches the trip level.",
            due_date=(today + datetime.timedelta(days=7)).isoformat()))

    # Optimised schedule: next statutory inspection + next preventive maintenance.
    report.schedule = _schedule(g, asset, inspections, work_orders, today)

    # Narrative: LLM if available, else a grounded template.
    report.narrative = _narrate(report, asset, llm)
    return report


def _schedule(g, asset, inspections, work_orders, today) -> List[dict]:
    out = []
    node = g.nodes.get(("Asset", asset))
    cls = (node.properties.get("asset_class") if node else "") or ""
    interval = _INTERVAL_BY_CLASS.get(cls)
    last_insp = max((_parse_date(i.properties.get("last_inspection_date"))
                     for i, _e in inspections
                     if _parse_date(i.properties.get("last_inspection_date"))), default=None)
    if interval and last_insp:
        due = last_insp + datetime.timedelta(days=interval)
        out.append({"task": f"Statutory inspection ({cls})",
                    "due_date": due.isoformat(),
                    "basis": f"last {last_insp.isoformat()} + {interval}d cycle"})
    crit = (node.properties.get("criticality") if node else "") or "Medium"
    pm_days = _PM_DAYS.get(crit, 180)
    last_wo = max((_parse_date(w.properties.get("date"))
                   for w, _e in work_orders if _parse_date(w.properties.get("date"))),
                  default=None)
    base = last_wo or today
    out.append({"task": "Preventive maintenance",
                "due_date": (base + datetime.timedelta(days=pm_days)).isoformat(),
                "basis": f"{crit} criticality -> {pm_days}d cadence"})
    return out


def _narrate(report: RCAReport, asset: str, llm) -> str:
    if llm is None or not report.findings:
        top = report.findings[0].cause if report.findings else "insufficient signals"
        return (f"Most likely root cause for {asset}: {top}. "
                f"{len(report.findings)} finding(s) considered from history and "
                f"operating conditions.")
    facts = "; ".join(f"{f.cause} ({f.rationale})" for f in report.findings[:5])
    prompt = (f"Write a 3-4 sentence root-cause summary for asset {asset} using ONLY "
              f"these findings: {facts}. State the most likely cause and the evidence.")
    try:
        return llm.generate(prompt, system="You are a reliability engineer. Be precise "
                                            "and do not invent facts.").strip()
    except Exception:
        return f"Most likely root cause for {asset}: {report.findings[0].cause}."
