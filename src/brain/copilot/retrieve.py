"""Hybrid GraphRAG retrieval — the five steps:
  1. detect the things the question is about (equipment tags)
  2. search passages by meaning (Neo4j vector index)
  3. expand: also take assets the top passages mention
  4. pull the connected facts for those assets from the graph
  5. hand both sets back for fusion into an answer
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from neo4j import GraphDatabase

from brain.config import settings
from brain.graph.resolve import canonical_asset_key
from brain.ontology import load_ontology, patterns as onto_patterns


def _driver():
    return GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))


def detect_asset_tags(question: str, session) -> List[str]:
    pat = onto_patterns(load_ontology()).get("equipment_tag", r"$^")
    candidates = {canonical_asset_key(t) for t in re.findall(pat, question, re.IGNORECASE)}
    found = []
    for tag in candidates:
        if session.run("MATCH (a:Asset {tag:$t}) RETURN a.tag AS t", t=tag).single():
            found.append(tag)
    return found


def detect_units(question: str, session) -> List[str]:
    ql = question.lower()
    rows = session.run("MATCH (u:Unit) RETURN u.name AS name")
    return [r["name"] for r in rows if r["name"] and r["name"].lower() in ql]


def assets_in_units(session, units: List[str]) -> List[str]:
    if not units:
        return []
    rows = session.run(
        "MATCH (a:Asset)-[:LOCATED_IN]->(u:Unit) WHERE u.name IN $u RETURN DISTINCT a.tag AS t", u=units)
    return [r["t"] for r in rows]


def detect_classes(question: str, session) -> List[str]:
    ql = question.lower()
    rows = session.run("MATCH (a:Asset) WHERE a.asset_class IS NOT NULL "
                       "RETURN DISTINCT a.asset_class AS c")
    out = []
    for r in rows:
        c = r["c"]
        if c and (c.lower() in ql or (c.lower() + "s") in ql):  # "valve" / "valves"
            out.append(c)
    return out


def assets_of_classes(session, classes: List[str]) -> List[str]:
    if not classes:
        return []
    rows = session.run("MATCH (a:Asset) WHERE a.asset_class IN $c RETURN a.tag AS t", c=classes)
    return [r["t"] for r in rows]


def vector_search(session, embedding: List[float], k: int = 6) -> List[Dict[str, Any]]:
    rows = session.run(
        "CALL db.index.vector.queryNodes('chunk_embeddings', $k, $emb) YIELD node, score "
        "OPTIONAL MATCH (node)-[:PART_OF]->(d:Document) "
        "RETURN node.id AS id, node.text AS text, score AS score, d.id AS doc, d.path AS path",
        k=k, emb=embedding)
    return [dict(r) for r in rows]


def assets_in_chunks(session, chunk_ids: List[str]) -> List[str]:
    if not chunk_ids:
        return []
    rows = session.run(
        "MATCH (c:Chunk)-[:MENTIONS]->(a:Asset) WHERE c.id IN $ids RETURN DISTINCT a.tag AS t",
        ids=chunk_ids)
    return [r["t"] for r in rows]


def _props_extras(props) -> str:
    props = props or {}
    return ", ".join(
        f"{k}={v}" for k, v in props.items()
        if k not in ("embedding", "text", "confidence", "source") and v is not None)


def graph_context(session, tags: List[str], limit: int = 30) -> List[Dict[str, Any]]:
    """Two-hop neighbourhood: the asset's direct facts AND one hop beyond
    (so e.g. Asset -> WorkOrder -> Person is reachable). De-duplicated.
    """
    facts: List[Dict[str, Any]] = []
    seen = set()

    def add(text: str, conf: float) -> None:
        if text and text not in seen:
            seen.add(text)
            facts.append({"text": text, "confidence": conf, "source": "knowledge graph"})

    for tag in tags:
        rows = session.run(
            "MATCH (a:Asset {tag:$tag})-[r1]-(n) WHERE NOT n:Chunk "
            "WITH a, r1, n LIMIT $lim "
            "OPTIONAL MATCH (n)-[r2]-(m) WHERE NOT m:Chunk AND elementId(m) <> elementId(a) "
            "RETURN type(r1) AS rel1, labels(n)[0] AS nl, "
            "coalesce(n.tag,n.wo_number,n.inspection_id,n.permit_no,n.code,n.name,n.id) AS nk, "
            "properties(n) AS nprops, coalesce(r1.confidence,0.8) AS conf1, "
            "type(r2) AS rel2, labels(m)[0] AS ml, "
            "coalesce(m.tag,m.wo_number,m.inspection_id,m.permit_no,m.code,m.name,m.id) AS mk, "
            "coalesce(r2.confidence,0.8) AS conf2",
            tag=tag, lim=limit)
        for r in rows:
            extras = _props_extras(r["nprops"])
            one = f"{tag} —[{r['rel1']}]— {r['nl']} {r['nk']}"
            add(f"{one} ({extras})" if extras else one, r["conf1"])
            if r["rel2"] and r["mk"] is not None:
                add(f"{r['nl']} {r['nk']} —[{r['rel2']}]— {r['ml']} {r['mk']}", r["conf2"])
    return facts


_EMBEDDER = None


def _embed(text: str) -> List[float]:
    global _EMBEDDER
    if _EMBEDDER is None:
        from brain.providers.embeddings import LocalEmbedder
        _EMBEDDER = LocalEmbedder()  # load the model once, reuse across calls
    return _EMBEDDER.embed([text])[0]


def retrieve(question: str, k: int = 6) -> Dict[str, Any]:
    embedding = _embed(question)
    driver = _driver()
    with driver.session() as s:
        tags = detect_asset_tags(question, s)
        units = detect_units(question, s)
        classes = detect_classes(question, s)
        chunks = vector_search(s, embedding, k)
        tags = list(dict.fromkeys(
            tags
            + assets_in_units(s, units)
            + assets_of_classes(s, classes)
            + assets_in_chunks(s, [c["id"] for c in chunks])))
        facts = graph_context(s, tags)
    driver.close()
    return {"question": question, "tags": tags, "chunks": chunks, "facts": facts}
