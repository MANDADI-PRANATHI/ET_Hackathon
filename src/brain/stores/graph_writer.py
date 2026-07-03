"""Persist the merged GraphModel into Neo4j.

Pure mechanics: MERGE each node by its (label, key), SET its properties, then
MERGE each relationship between the already-merged endpoints. Provenance
(confidence, extractors, needs_review) is written onto the elements so the
copilot can cite and score answers later.

Neo4j is imported lazily; if it isn't installed or reachable the caller can skip
the write (build_graph.py degrades to model + metrics + export).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from brain.config import settings
from brain.graph.model import GraphModel


def _key_map(onto: Dict[str, Any]) -> Dict[str, str]:
    return {n["label"]: n.get("key", "id") for n in onto["nodes"]}


def _clean_props(props: Dict[str, Any]) -> Dict[str, Any]:
    # Neo4j can't store None; drop empty values (keeps the node tidy).
    return {k: v for k, v in props.items() if v not in (None, "")}


def write_graph(g: GraphModel, onto: Dict[str, Any], driver=None, wipe: bool = False) -> Dict[str, int]:
    from neo4j import GraphDatabase

    close_after = False
    if driver is None:
        driver = GraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )
        close_after = True

    keys = _key_map(onto)
    counts = {"nodes": 0, "relationships": 0}

    with driver.session() as session:
        if wipe:
            session.run("MATCH (n) DETACH DELETE n")

        for (label, value), node in g.nodes.items():
            key = node.key or keys.get(label, "id")
            props = _clean_props(node.properties)
            props[key] = value
            session.run(
                f"MERGE (n:`{label}` {{`{key}`: $val}}) "
                f"SET n += $props, n._confidence = $conf, "
                f"n._extractors = $ex, n._needs_review = $nr, n._aliases = $al",
                val=value, props=props, conf=node.confidence,
                ex=sorted(set(node.extractors)), nr=node.needs_review,
                al=node.aliases,
            )
            counts["nodes"] += 1

        for edge in g.edges.values():
            fk = keys.get(edge.from_label, "id")
            tk = keys.get(edge.to_label, "id")
            fnode = g.nodes.get((edge.from_label, edge.from_value))
            tnode = g.nodes.get((edge.to_label, edge.to_value))
            fk = (fnode.key if fnode else fk) or fk
            tk = (tnode.key if tnode else tk) or tk
            session.run(
                f"MATCH (a:`{edge.from_label}` {{`{fk}`: $fv}}), "
                f"(b:`{edge.to_label}` {{`{tk}`: $tv}}) "
                f"MERGE (a)-[r:`{edge.type}`]->(b) "
                f"SET r._confidence = $conf, r._extractors = $ex, r._needs_review = $nr",
                fv=edge.from_value, tv=edge.to_value, conf=edge.confidence,
                ex=sorted(set(edge.extractors)), nr=edge.needs_review,
            )
            counts["relationships"] += 1

    if close_after:
        driver.close()
    return counts
