"""Load the staged facts (data/staging/*.json) into Neo4j as the asset-centric graph.

On the way in it:
  - MERGEs nodes by their canonical key (so duplicates collapse into one),
  - keeps each node's highest confidence,
  - only inserts relationships whose (from -> type -> to) shape the ontology allows,
  - loads chunks (with their meaning-fingerprints) and links them to their document,
  - links each chunk to any asset it mentions (regex, no AI),
  - and reports linkage-completeness (a judged metric).
"""
from __future__ import annotations

import json
import pathlib
import re
from typing import Any, Dict

from neo4j import GraphDatabase

from brain.config import settings
from brain.graph.resolve import canonical_asset_key
from brain.graph.validate import allowed_triples
from brain.ontology import load_ontology, patterns as onto_patterns

# Confidence floor by method when the source didn't give a usable one.
METHOD_CONF = {"structured": 1.0, "rule": 0.9, "ai": 0.6, "vision": 0.7}


def _conf(method: str, raw: Any) -> float:
    try:
        v = float(raw)
    except (TypeError, ValueError):
        v = 0.0
    return v if v > 0 else METHOD_CONF.get(method, 0.5)


def _canon(label: str, key: str) -> str:
    return canonical_asset_key(key) if label == "Asset" else (key or "").strip()


def load_staging(staging_dir: str = "data/staging") -> Dict[str, Any]:
    onto = load_ontology()
    allowed = allowed_triples(onto)
    key_prop = {n["label"]: n["key"] for n in onto["nodes"] if n.get("key")}
    tag_re = re.compile(onto_patterns(onto).get("equipment_tag", r"$^"))

    driver = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
    stats = {"documents": 0, "entities": 0, "relations": 0,
             "relations_dropped": 0, "chunks": 0, "chunk_mentions": 0}
    with driver.session() as session:
        for jf in sorted(pathlib.Path(staging_dir).glob("*.json")):
            _load_doc(session, json.loads(jf.read_text(encoding="utf-8")),
                      allowed, key_prop, tag_re, stats)
        stats.update(_linkage(session))
    driver.close()
    return stats


def _load_doc(session, doc, allowed, key_prop, tag_re, stats) -> None:
    doc_id = doc["document_id"]
    session.run("MERGE (d:Document {id:$id}) SET d.doc_type=$t, d.path=$p",
                id=doc_id, t=doc.get("doc_type"), p=doc.get("path"))
    stats["documents"] += 1

    # ---- entities ----
    for e in doc.get("entities", []):
        label = e.get("label")
        if label not in key_prop:
            continue
        kp = key_prop[label]
        key = _canon(label, str(e.get("key", "")))
        if not key:
            continue
        props = {k: v for k, v in (e.get("properties") or {}).items() if k != kp and v is not None}
        conf = _conf(e.get("method"), e.get("confidence"))
        session.run(
            f"MERGE (n:`{label}` {{`{kp}`:$key}}) "
            f"SET n += $props, "
            f"n.confidence = CASE WHEN coalesce(n.confidence,0) < $conf THEN $conf ELSE n.confidence END",
            key=key, props=props, conf=conf)
        stats["entities"] += 1

    # ---- relationships (validated against the ontology) ----
    for r in doc.get("relations", []):
        fl, typ, tl = r.get("from_label"), r.get("type"), r.get("to_label")
        if (fl, typ, tl) not in allowed:
            stats["relations_dropped"] += 1
            continue
        fk, tk = _canon(fl, str(r.get("from_key", ""))), _canon(tl, str(r.get("to_key", "")))
        if not fk or not tk:
            stats["relations_dropped"] += 1
            continue
        conf = _conf(r.get("method"), r.get("confidence"))
        session.run(
            f"MERGE (a:`{fl}` {{`{key_prop[fl]}`:$fk}}) "
            f"MERGE (b:`{tl}` {{`{key_prop[tl]}`:$tk}}) "
            f"MERGE (a)-[rel:`{typ}`]->(b) SET rel.confidence=$conf, rel.source=$src",
            fk=fk, tk=tk, conf=conf, src=r.get("source"))
        stats["relations"] += 1

    # ---- chunks (+ MENTIONS to any asset they name) ----
    for c in doc.get("chunks", []):
        cid = c.get("id")
        if not cid:
            continue
        session.run(
            "MERGE (c:Chunk {id:$id}) SET c.text=$text, c.page=$page, c.embedding=$emb "
            "WITH c MATCH (d:Document {id:$doc}) MERGE (c)-[:PART_OF]->(d)",
            id=cid, text=c.get("text"), page=c.get("page"), emb=c.get("embedding"), doc=doc_id)
        stats["chunks"] += 1
        for tag in {canonical_asset_key(t) for t in tag_re.findall(c.get("text") or "")}:
            res = session.run(
                "MATCH (a:Asset {tag:$tag}) WITH a MATCH (c:Chunk {id:$id}) "
                "MERGE (c)-[:MENTIONS]->(a) RETURN count(a) AS n",
                tag=tag, id=cid).single()
            if res and res["n"]:
                stats["chunk_mentions"] += 1


def _linkage(session) -> Dict[str, Any]:
    total = session.run(
        "MATCH (n) WHERE NOT n:Chunk AND NOT n:Document RETURN count(n) AS c").single()["c"]
    linked = session.run(
        "MATCH (n) WHERE NOT n:Chunk AND NOT n:Document AND (n)--() "
        "RETURN count(n) AS c").single()["c"]
    nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
    rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
    pct = round(100.0 * linked / total, 1) if total else 0.0
    return {"graph_nodes_total": nodes, "graph_relationships_total": rels,
            "linkage_completeness_pct": pct}
