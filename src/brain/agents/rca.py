"""Level 4b — Root Cause Analysis / failure investigator.

Fuses an asset's maintenance & failure records (from the graph) with its recent
sensor readings (from the readings adapter), then the AI reasons over that
evidence to produce a root cause, predictive recommendation, and an optimised
maintenance schedule. The anomaly detection is plain code; the reasoning is AI.
"""
from __future__ import annotations

import pathlib
from typing import Any, Dict, Optional

from neo4j import GraphDatabase

from brain.agents.readings import readable, summarize
from brain.config import settings
from brain.copilot.retrieve import graph_context

SYSTEM = (
    "You are a reliability / maintenance engineer performing Root Cause Analysis. "
    "Use ONLY the evidence provided. Be concise, specific and practical. If the "
    "evidence is insufficient for a confident conclusion, say so."
)


def gather(asset_tag: str) -> Dict[str, Any]:
    driver = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
    with driver.session() as s:
        facts = graph_context(s, [asset_tag])
    driver.close()
    return {"asset": asset_tag, "facts": facts, "readings": summarize(asset_tag)}


def investigate(asset_tag: str, llm=None) -> Dict[str, Any]:
    ctx = gather(asset_tag)
    fact_block = "\n".join(f"- {f['text']}" for f in ctx["facts"]) or "(none)"
    read_block = readable(ctx["readings"])

    if llm is None:
        from brain.providers.llm import get_llm
        llm = get_llm()

    prompt = (
        f"ASSET: {asset_tag}\n\n"
        f"MAINTENANCE & RECORDS (from the knowledge graph):\n{fact_block}\n\n"
        f"SENSOR READINGS (last 60 days):\n{read_block}\n\n"
        "Produce:\n"
        "1. LIKELY ROOT CAUSE — name an ISO 14224-style failure mode if applicable.\n"
        "2. EVIDENCE — cite the specific facts and readings you relied on.\n"
        "3. PREDICTIVE MAINTENANCE RECOMMENDATION.\n"
        "4. OPTIMISED MAINTENANCE SCHEDULE — next actions with suggested timing/intervals."
    )
    analysis = llm.generate(prompt, system=SYSTEM)
    return {"asset": asset_tag, "analysis": analysis, "facts": ctx["facts"], "readings": ctx["readings"]}


def write_report(result: Dict[str, Any], path: Optional[str] = None) -> pathlib.Path:
    asset = result["asset"]
    out = pathlib.Path(path or f"reports/rca_{asset}.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# Root Cause Analysis — {asset}", "", result["analysis"], "",
             "## Evidence — sensor readings", "```", readable(result["readings"]), "```", "",
             "## Evidence — maintenance & records"]
    lines += [f"- {f['text']}" for f in result["facts"]] or ["(none)"]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
