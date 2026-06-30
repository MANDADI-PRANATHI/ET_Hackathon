"""Level 4a — Quality & Compliance checker (hybrid: AI derives rules, code decides).

  derive_rules_from_text() : AI turns regulation prose into checkable rules
  check_rule()             : PLAIN CODE evaluates a rule against the graph -> met/gap/unknown
  run_compliance()         : run all rules, return findings (with evidence)
  write_evidence_pack()    : audit-ready Markdown report (+ AI executive summary)
"""
from __future__ import annotations

import datetime
import json
import pathlib
import re
from typing import Any, Dict, List, Optional

import yaml
from neo4j import GraphDatabase

from brain.config import settings

TODAY = datetime.date.today()
DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y")


def _driver():
    return GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))


def load_rules(path: str = "config/compliance_rules.yaml") -> List[Dict[str, Any]]:
    return yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))["rules"]


def _parse_date(s: Optional[str]):
    for fmt in DATE_FORMATS:
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def _finding(asset, rule, status, detail, evidence) -> Dict[str, Any]:
    return {"asset": asset, "status": status, "detail": detail, "evidence": evidence,
            "rule_id": rule["id"], "requirement": rule["description"], "source": rule.get("source", "")}


def check_rule(session, rule: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The deterministic decision-maker — no AI here."""
    ct = rule["check_type"]
    cls = rule.get("applies_to_class")
    out: List[Dict[str, Any]] = []

    if ct == "inspection_interval":
        limit = int(rule["interval_days"])
        rows = session.run(
            "MATCH (a:Asset {asset_class:$cls}) "
            "OPTIONAL MATCH (a)<-[:INSPECTS]-(i:Inspection) "
            "RETURN a.tag AS tag, max(i.last_inspection_date) AS last", cls=cls)
        for r in rows:
            last = _parse_date(r["last"])
            if last is None:
                out.append(_finding(r["tag"], rule, "gap", "No inspection record found", None))
                continue
            days = (TODAY - last).days
            if days > limit:
                out.append(_finding(r["tag"], rule, "gap",
                    f"Last inspection {last.isoformat()} was {days} days ago; limit is {limit} days",
                    last.isoformat()))
            else:
                out.append(_finding(r["tag"], rule, "met",
                    f"Last inspection {last.isoformat()} ({days} days ago), within {limit} days",
                    last.isoformat()))

    elif ct == "no_open_nonconformance":
        rows = session.run(
            "MATCH (a:Asset {asset_class:$cls}) "
            "OPTIONAL MATCH (a)<-[:RAISED_AGAINST]-(n:NonConformance {status:'Open'}) "
            "RETURN a.tag AS tag, collect(n.id) AS ncrs", cls=cls)
        for r in rows:
            ncrs = [x for x in r["ncrs"] if x]
            if ncrs:
                out.append(_finding(r["tag"], rule, "gap",
                    f"Open non-conformance(s): {', '.join(ncrs)}", ", ".join(ncrs)))
            else:
                out.append(_finding(r["tag"], rule, "met", "No open non-conformances", None))

    elif ct == "record_exists":
        label = rule["requires_label"]
        rows = session.run(
            f"MATCH (a:Asset {{asset_class:$cls}}) "
            f"OPTIONAL MATCH (a)--(x:`{label}`) "
            f"RETURN a.tag AS tag, count(x) AS n", cls=cls)
        for r in rows:
            if r["n"] > 0:
                out.append(_finding(r["tag"], rule, "met", f"Has {r['n']} linked {label} record(s)", None))
            else:
                out.append(_finding(r["tag"], rule, "gap", f"No linked {label} record", None))

    return out


def run_compliance(rules_path: str = "config/compliance_rules.yaml") -> List[Dict[str, Any]]:
    rules = load_rules(rules_path)
    driver = _driver()
    findings: List[Dict[str, Any]] = []
    with driver.session() as s:
        for rule in rules:
            findings.extend(check_rule(s, rule))
    driver.close()
    return findings


def derive_rules_from_text(text: str, llm=None) -> List[Dict[str, Any]]:
    """The AI half of the hybrid: turn regulation prose into checkable rules."""
    if llm is None:
        from brain.providers.llm import get_llm
        llm = get_llm()
    schema = ('[{"id":"REQ-..","description":"..","applies_to_class":'
              '"Pump|Valve|Vessel|Compressor|HeatExchanger|Instrument",'
              '"check_type":"inspection_interval|no_open_nonconformance|record_exists",'
              '"interval_days":N,"requires_label":".."}]')
    raw = llm.generate(
        f"Convert this regulation text into machine-checkable compliance rules as a JSON list. "
        f"Use ONLY these check_type values: inspection_interval (with interval_days), "
        f"no_open_nonconformance, record_exists (with requires_label). Only include rules clearly "
        f"supported by the text. Schema: {schema}\n\nTEXT:\n{text[:4000]}",
        system="Return STRICT JSON only.")
    m = re.search(r"\[.*\]", raw, re.S)
    try:
        return json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        return []


def write_evidence_pack(findings: List[Dict[str, Any]],
                        path: str = "reports/compliance_report.md",
                        use_llm: bool = True) -> pathlib.Path:
    gaps = [f for f in findings if f["status"] == "gap"]
    rule_ids: List[str] = []
    for f in findings:
        if f["rule_id"] not in rule_ids:
            rule_ids.append(f["rule_id"])

    body: List[str] = []
    for rid in rule_ids:
        group = [f for f in findings if f["rule_id"] == rid]
        s = group[0]
        body.append(f"## {rid} — {s['requirement']}")
        if s.get("source"):
            body.append(f"_Source: {s['source']}_")
        body.append("")
        for f in group:
            mark = {"gap": "❌ **GAP**", "met": "✅ MET", "unknown": "❓ UNKNOWN"}.get(f["status"], "?")
            body.append(f"- **{f['asset']}** — {mark}: {f['detail']}")
        body.append("")

    summary: List[str] = []
    if use_llm and gaps:
        try:
            from brain.providers.llm import get_llm
            text = get_llm().generate(
                "Write a 3-5 sentence executive summary plus a prioritised corrective-action list "
                "for these plant compliance gaps:\n"
                + "\n".join(f"- {g['asset']}: {g['requirement']} — {g['detail']}" for g in gaps),
                system="You are a plant compliance officer. Be concise, practical and audit-appropriate.")
            summary = ["## Executive summary", text, ""]
        except Exception as e:  # noqa: BLE001
            summary = [f"_(AI summary unavailable: {e})_", ""]

    header = [
        "# Compliance Evidence Pack", "",
        f"_Generated {TODAY.isoformat()}_", "",
        f"**Result:** {len(findings)} checks across {len(rule_ids)} requirements — "
        f"**{len(gaps)} gap(s)**, {len(findings) - len(gaps)} compliant.", "",
    ]
    out = pathlib.Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(header + summary + body), encoding="utf-8")
    return out
