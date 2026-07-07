"""Compliance & QMS agent — hybrid by design.

Real compliance is not a "vibe check": "was this valve inspected within 6 months?"
is an exact date comparison, not an opinion. So we split the work:

  - the LLM *reads* a regulation clause and turns it into a precise, checkable
    RegRequirement (which asset class, what kind of check, the interval/threshold);
  - a PLAIN-CODE evaluator runs that rule against the actual graph data and
    returns a hard MET / GAP / UNKNOWN. The yes/no decision is never left to a
    model's guess.

A curated rule library ships with the profile so the check runs fully offline;
the LLM parser (parse_clause) is how new rules get authored from regulation text.
The agent then produces an audit-ready evidence package and drafts a
non-conformance + corrective action (CAPA) for every gap.
"""
from __future__ import annotations

import datetime
import json
import re
from dataclasses import dataclass, field
from typing import List, Optional

from brain.graph.model import GraphModel
from brain.schema import SourceRef

MET, GAP, UNKNOWN = "MET", "GAP", "UNKNOWN"


@dataclass
class RegRequirement:
    """A machine-checkable rule derived from a regulation clause."""

    id: str
    code: str                      # e.g. OISD-STD-105
    clause: str                    # human text the rule came from
    applies_to_class: str          # asset class the rule governs, e.g. "Valve"
    check_type: str                # "interval_days" | "no_open_nonconformance" | "record_exists" | "threshold"
    interval_days: Optional[int] = None
    parameter: Optional[str] = None
    operator: Optional[str] = None   # for threshold checks (<=, >=, ...)
    threshold: Optional[float] = None
    requires_label: Optional[str] = None   # for "record_exists" checks
    description: str = ""


# --- curated rule library (ships with the oil & gas profile) ---------------
RULESET: List[RegRequirement] = [
    RegRequirement(
        id="REQ-OISD105-VALVE-INSP", code="OISD-STD-105",
        clause="Pressure relief valves shall be tested/inspected at intervals not "
               "exceeding six months.",
        applies_to_class="Valve", check_type="interval_days", interval_days=182,
        description="Statutory 6-month inspection cycle for pressure safety/relief valves.",
    ),
    RegRequirement(
        id="REQ-OISD105-VESSEL-INSP", code="OISD-STD-105",
        clause="Pressure vessels shall be internally inspected at intervals not "
               "exceeding the statutory period.",
        applies_to_class="Vessel", check_type="interval_days", interval_days=365,
        description="Annual inspection cycle for pressure vessels.",
    ),
]


@dataclass
class AssetCompliance:
    asset: str
    requirement_id: str
    code: str
    status: str                    # MET | GAP | UNKNOWN
    detail: str
    last_date: Optional[str] = None
    days_since: Optional[int] = None
    interval_days: Optional[int] = None
    evidence: Optional[SourceRef] = None


@dataclass
class ComplianceReport:
    assessed_on: str
    results: List[AssetCompliance] = field(default_factory=list)

    @property
    def gaps(self) -> List[AssetCompliance]:
        return [r for r in self.results if r.status == GAP]

    @property
    def summary(self) -> dict:
        s = {MET: 0, GAP: 0, UNKNOWN: 0}
        for r in self.results:
            s[r.status] += 1
        return s

    def to_markdown(self) -> str:
        lines = ["# Compliance Evidence Package",
                 f"_Assessed on {self.assessed_on}_\n",
                 f"**Summary:** {self.summary[MET]} met · {self.summary[GAP]} gaps · "
                 f"{self.summary[UNKNOWN]} unknown\n",
                 "| Asset | Regulation | Requirement | Status | Detail |",
                 "|---|---|---|---|---|"]
        for r in sorted(self.results, key=lambda x: (x.status != GAP, x.asset)):
            lines.append(f"| {r.asset} | {r.code} | {r.requirement_id} | "
                         f"**{r.status}** | {r.detail} |")
        if self.gaps:
            lines.append("\n## Gaps requiring action")
            for g in self.gaps:
                src = g.evidence.path if g.evidence else "—"
                lines.append(f"- **{g.asset}** ({g.code}): {g.detail}  \n"
                             f"  Evidence: `{src}`")
        return "\n".join(lines)

    def drafts(self) -> List[dict]:
        """Draft a non-conformance + CAPA for each gap (QMS output)."""
        out = []
        for i, g in enumerate(self.gaps, start=1):
            out.append({
                "non_conformance": {
                    "id": f"NCR-AUTO-{i:03d}", "asset": g.asset,
                    "finding": g.detail, "raised_date": self.assessed_on,
                    "source_regulation": g.code, "status": "Open",
                },
                "capa": {
                    "id": f"CAPA-AUTO-{i:03d}",
                    "action": f"Schedule and complete the required check for {g.asset} "
                              f"per {g.code}; update inspection records.",
                    "due_date": _add_days(self.assessed_on, 14), "status": "Open",
                },
            })
        return out


def _parse_date(s: Optional[str]) -> Optional[datetime.date]:
    if not s:
        return None
    try:
        return datetime.date.fromisoformat(s.strip()[:10])
    except ValueError:
        return None


def _add_days(iso: str, days: int) -> str:
    d = _parse_date(iso) or datetime.date.today()
    return (d + datetime.timedelta(days=days)).isoformat()


def _latest_inspection(g: GraphModel, asset_value: str):
    """The most recent Inspection connected to an asset (node, date)."""
    best_node, best_date = None, None
    for edge in g.edges_to("Asset", asset_value):
        if edge.type != "INSPECTS":
            continue
        insp = g.nodes.get((edge.from_label, edge.from_value))
        if insp is None:
            continue
        d = _parse_date(insp.properties.get("last_inspection_date"))
        if d and (best_date is None or d > best_date):
            best_node, best_date = insp, d
    return best_node, best_date


def _assets_of_class(g: GraphModel, asset_class: str):
    for asset in g.nodes_by_label("Asset"):
        if (asset.properties.get("asset_class") or "") == asset_class:
            yield asset


def _check_interval_days(g: GraphModel, req: RegRequirement, today: datetime.date):
    results: List[AssetCompliance] = []
    for asset in _assets_of_class(g, req.applies_to_class):
        insp, last = _latest_inspection(g, asset.value)
        if insp is None or last is None:
            results.append(AssetCompliance(
                asset=asset.value, requirement_id=req.id, code=req.code,
                status=UNKNOWN, detail="No inspection record found.",
                interval_days=req.interval_days))
            continue
        days = (today - last).days
        evidence = insp.sources[0] if insp.sources else None
        if days > req.interval_days:
            detail = (f"Last inspection {last.isoformat()} was {days} days ago — "
                      f"exceeds the {req.interval_days}-day limit by "
                      f"{days - req.interval_days} days.")
            status = GAP
        else:
            detail = (f"Last inspection {last.isoformat()} ({days} days ago) is "
                      f"within the {req.interval_days}-day limit.")
            status = MET
        results.append(AssetCompliance(
            asset=asset.value, requirement_id=req.id, code=req.code, status=status,
            detail=detail, last_date=last.isoformat(), days_since=days,
            interval_days=req.interval_days, evidence=evidence))
    return results


def _check_no_open_nonconformance(g: GraphModel, req: RegRequirement):
    """MET unless an open NonConformance is raised against the asset."""
    results: List[AssetCompliance] = []
    for asset in _assets_of_class(g, req.applies_to_class):
        open_ncrs = []
        for edge in g.edges_to("Asset", asset.value):
            if edge.type != "RAISED_AGAINST":
                continue
            ncr = g.nodes.get((edge.from_label, edge.from_value))
            if ncr is not None and (ncr.properties.get("status") or "").lower() == "open":
                open_ncrs.append(ncr.value)
        if open_ncrs:
            results.append(AssetCompliance(
                asset=asset.value, requirement_id=req.id, code=req.code, status=GAP,
                detail=f"Open non-conformance(s): {', '.join(open_ncrs)}"))
        else:
            results.append(AssetCompliance(
                asset=asset.value, requirement_id=req.id, code=req.code, status=MET,
                detail="No open non-conformances."))
    return results


def _check_record_exists(g: GraphModel, req: RegRequirement):
    """MET if the asset has at least one linked node of the required label."""
    results: List[AssetCompliance] = []
    label = req.requires_label
    for asset in _assets_of_class(g, req.applies_to_class):
        linked = [e for e in (g.edges_from("Asset", asset.value) + g.edges_to("Asset", asset.value))
                  if e.from_label == label or e.to_label == label]
        if linked:
            results.append(AssetCompliance(
                asset=asset.value, requirement_id=req.id, code=req.code, status=MET,
                detail=f"Has {len(linked)} linked {label} record(s)."))
        else:
            results.append(AssetCompliance(
                asset=asset.value, requirement_id=req.id, code=req.code, status=GAP,
                detail=f"No linked {label} record."))
    return results


def check_requirement(
    g: GraphModel, req: RegRequirement, today: datetime.date
) -> List[AssetCompliance]:
    if req.check_type == "interval_days" and req.interval_days:
        return _check_interval_days(g, req, today)
    if req.check_type == "no_open_nonconformance":
        return _check_no_open_nonconformance(g, req)
    if req.check_type == "record_exists" and req.requires_label:
        return _check_record_exists(g, req)
    return []   # threshold checks arrive with Level 4b readings


def run_compliance(
    g: GraphModel,
    ruleset: Optional[List[RegRequirement]] = None,
    today: Optional[datetime.date] = None,
) -> ComplianceReport:
    ruleset = ruleset if ruleset is not None else RULESET
    today = today or datetime.date.today()
    report = ComplianceReport(assessed_on=today.isoformat())
    for req in ruleset:
        report.results.extend(check_requirement(g, req, today))
    return report


# --- LLM clause -> rule (how new rules are authored; injected, offline-safe) --

_PARSE_SYSTEM = (
    "You convert a regulation clause into a strict, machine-checkable rule. "
    "You never decide compliance yourself — you only describe the check."
)


def parse_clause(text: str, code: str, llm, applies_hint: str = "") -> List[RegRequirement]:
    """Use the LLM to author RegRequirements from clause text (best-effort)."""
    if llm is None or not text.strip():
        return []
    prompt = (
        "Convert the clause into a JSON array of rules. Each rule: "
        '{"applies_to_class": <AssetClass>, "check_type": "interval_days", '
        '"interval_days": <int>, "description": <short>}. '
        f"Regulation code: {code}. {('Likely class: ' + applies_hint) if applies_hint else ''}\n"
        "Return ONLY the JSON array.\n\nCLAUSE:\n" + text
    )
    try:
        raw = llm.generate(prompt, system=_PARSE_SYSTEM)
    except Exception:
        return []
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        return []
    try:
        items = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out = []
    for i, it in enumerate(items):
        cls = it.get("applies_to_class")
        interval = it.get("interval_days")
        if not cls or not isinstance(interval, int):
            continue
        out.append(RegRequirement(
            id=f"REQ-{code}-{cls}-{i}".upper().replace(" ", ""), code=code,
            clause=text[:300], applies_to_class=cls, check_type="interval_days",
            interval_days=interval, description=it.get("description", "")))
    return out
