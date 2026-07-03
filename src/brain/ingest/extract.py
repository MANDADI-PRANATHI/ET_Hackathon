"""AI extraction for facts that live *in prose* — the last resort, deliberately.

Structured tables and predictable identifiers are handled without AI (see
structured.py / patterns.py). This module is only for facts a human has to read a
sentence to know: "the seal failed because of misalignment", "this SOP governs
P-101A", "the relief setpoint is 12 barg".

The model is fenced in hard:
  - it may only use node/relationship types from the loaded ontology,
  - every fact must quote the exact source sentence (`evidence`) — that powers
    the citation and lets a human check it,
  - output must be JSON matching a strict shape; anything malformed is dropped,
  - confidence is capped (prose extraction never outranks a table reading).

The LLM is injected (any object with `.generate(prompt, system=None)`), so this
is testable with a stub and swaps providers for free.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from brain.ingest.confidence import base, clamp
from brain.schema import AI, EdgeFact, NodeFact, SourceRef

_AI_CONFIDENCE_CAP = 0.85   # prose extraction never beats a structured reading

_SYSTEM = (
    "You are an industrial knowledge engineer extracting facts from plant "
    "documents. You are precise and never invent tags, causes, or numbers. "
    "You only report facts a specific sentence in the text supports, and you "
    "quote that sentence."
)


def _label_key_map(onto: Dict[str, Any]) -> Dict[str, str]:
    return {n["label"]: n.get("key") for n in onto["nodes"]}


def _rel_index(onto: Dict[str, Any]) -> Dict[str, Tuple[str, str]]:
    """relation type -> (from_label, to_label), first declared direction."""
    idx: Dict[str, Tuple[str, str]] = {}
    for r in onto["relationships"]:
        idx.setdefault(r["type"], (r["from"], r["to"]))
    return idx


def build_prompt(text: str, onto: Dict[str, Any]) -> str:
    labels = [n["label"] for n in onto["nodes"]]
    rels = sorted({r["type"] for r in onto["relationships"]})
    return (
        "From the TEXT below, extract facts as a JSON array. Each item:\n"
        '  {"subject": <name/tag>, "subject_type": <NodeType>,\n'
        '   "relation": <RelationType>, "object": <name/tag>,\n'
        '   "object_type": <NodeType>, "evidence": <exact source sentence>,\n'
        '   "confidence": <0..1>}\n\n'
        f"Allowed NodeTypes: {', '.join(labels)}\n"
        f"Allowed RelationTypes: {', '.join(rels)}\n\n"
        "Rules: only facts the text explicitly supports; copy the evidence "
        "sentence verbatim; prefer equipment tags exactly as written; if nothing "
        "qualifies, return []. Return ONLY the JSON array.\n\n"
        f"TEXT:\n{text}"
    )


def _parse_json_array(raw: str) -> List[dict]:
    """Pull a JSON array out of the model's reply, tolerating code fences/prose."""
    if not raw:
        return []
    fenced = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE)
    start, end = fenced.find("["), fenced.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        data = json.loads(fenced[start : end + 1])
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _node_value(doc_id: str, label: str, name: str, key: Optional[str]) -> Optional[str]:
    """Key value for a node. Labels whose key is a machine id (not a human name)
    get a synthetic, stable id derived from the document + name."""
    if not key:
        return None
    if key in {"id"} and label in {"Incident", "NonConformance", "CAPA", "RegClause",
                                   "RegRequirement", "Parameter"}:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()[:40]
        return f"{doc_id}:{label.lower()}:{slug}"
    return name


def parse_facts(
    items: List[dict], onto: Dict[str, Any], source: SourceRef
) -> Tuple[List[NodeFact], List[EdgeFact]]:
    keys = _label_key_map(onto)
    rels = _rel_index(onto)
    nodes: List[NodeFact] = []
    edges: List[EdgeFact] = []

    for it in items:
        try:
            s_label, o_label = it["subject_type"], it["object_type"]
            relation = it["relation"]
            s_name, o_name = str(it["subject"]).strip(), str(it["object"]).strip()
        except (KeyError, TypeError):
            continue
        if s_label not in keys or o_label not in keys or relation not in rels:
            continue

        conf = it.get("confidence")
        conf = clamp(float(conf)) if isinstance(conf, (int, float)) else base(AI)
        conf = min(conf, _AI_CONFIDENCE_CAP)
        src = source.model_copy(update={"evidence": (it.get("evidence") or source.evidence)})

        s_val = _node_value(source.doc_id, s_label, s_name, keys[s_label])
        o_val = _node_value(source.doc_id, o_label, o_name, keys[o_label])
        if not s_val or not o_val:
            continue

        nodes.append(NodeFact(label=s_label, key=keys[s_label], value=s_val,
                              properties={keys[s_label]: s_val, "name": s_name},
                              source=src, confidence=conf, extractor=AI))
        nodes.append(NodeFact(label=o_label, key=keys[o_label], value=o_val,
                              properties={keys[o_label]: o_val, "name": o_name},
                              source=src, confidence=conf, extractor=AI))
        # Orient the edge to the ontology's declared direction.
        from_label, _to_label = rels[relation]
        if from_label == s_label:
            edges.append(EdgeFact(type=relation, from_label=s_label, from_value=s_val,
                                  to_label=o_label, to_value=o_val, source=src,
                                  confidence=conf, extractor=AI))
        else:
            edges.append(EdgeFact(type=relation, from_label=o_label, from_value=o_val,
                                  to_label=s_label, to_value=s_val, source=src,
                                  confidence=conf, extractor=AI))
    return nodes, edges


def extract_prose_facts(
    text: str, source: SourceRef, onto: Dict[str, Any], llm
) -> Tuple[List[NodeFact], List[EdgeFact]]:
    """Run the model over one passage and return validated node/edge facts."""
    if not text.strip() or llm is None:
        return [], []
    try:
        raw = llm.generate(build_prompt(text, onto), system=_SYSTEM)
    except Exception:      # a model hiccup must never crash ingestion
        return [], []
    return parse_facts(_parse_json_array(raw), onto, source)
