"""AI extraction for facts buried in prose (incident reports, procedures, emails).

The AI is fenced in: it may only use the ontology's allowed entity types/labels,
must return strict JSON, and each fact carries an evidence quote + confidence.
Works with whichever provider is configured (Gemini or Ollama).
"""
from __future__ import annotations

import json
import re
from typing import List, Tuple

from brain.ingest.models import ExtractedEntity, ExtractedRelation
from brain.ontology import load_ontology


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    match = re.search(r"\{.*\}", raw, re.S)  # tolerate code fences / preamble
    if not match:
        return {"entities": [], "relations": []}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"entities": [], "relations": []}


def extract_from_text(text: str, source: str, llm=None) -> Tuple[List[ExtractedEntity], List[ExtractedRelation]]:
    onto = load_ontology()
    labels = [n["label"] for n in onto["nodes"]]
    entity_types = onto.get("extract_entities", [])
    rel_types = sorted({r["type"] for r in onto["relationships"]})

    if llm is None:
        from brain.providers.llm import get_llm
        llm = get_llm()

    system = (
        "You extract structured industrial facts from text. "
        "Only use the allowed node labels and relationship types. "
        "Only extract facts explicitly supported by the text. Return STRICT JSON only."
    )
    prompt = f"""Allowed node labels: {labels}
Entity kinds to look for: {entity_types}
Allowed relationship types: {rel_types}

Return JSON exactly in this shape:
{{"entities":[{{"label":"Asset","key":"P-101A","properties":{{}},"confidence":0.0,"evidence":"short quote"}}],
  "relations":[{{"type":"MAINTAINS","from_label":"WorkOrder","from_key":"WO-1","to_label":"Asset","to_key":"P-101A","confidence":0.0}}]}}

TEXT:
{text[:6000]}"""

    data = _parse_json(llm.generate(prompt, system=system))

    entities = [
        ExtractedEntity(
            e["label"], str(e["key"]), e.get("properties", {}) or {},
            source=f"{source}: {str(e.get('evidence', ''))[:80]}",
            confidence=float(e.get("confidence", 0.6)), method="ai")
        for e in data.get("entities", []) if e.get("label") in labels and e.get("key")
    ]
    relations = [
        ExtractedRelation(
            r["type"], r["from_label"], str(r["from_key"]), r["to_label"], str(r["to_key"]),
            source=source, confidence=float(r.get("confidence", 0.6)), method="ai")
        for r in data.get("relations", []) if r.get("type") in rel_types
    ]
    return entities, relations
