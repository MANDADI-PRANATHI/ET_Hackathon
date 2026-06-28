"""Level 2: build the knowledge graph in Neo4j from the staged facts.

  python scripts/build_graph.py     (or: make build-graph)
Requires Neo4j running (make up) and Level 1 staging present (make ingest).
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from brain.graph.loader import load_staging  # noqa: E402
from brain.stores.neo4j_init import init_schema  # noqa: E402


def main() -> None:
    print("Ensuring Neo4j schema (constraints + vector index)...\n")
    init_schema()
    print("\nLoading staged facts into the graph...\n")
    stats = load_staging()
    print("Graph build complete:\n")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(
        "\nExplore it at  http://localhost:7474\n"
        "  Try:  MATCH (a:Asset)-[r]-(n) RETURN a, r, n LIMIT 100\n"
        "  Or:   MATCH (a:Asset {tag:'P-101B'})-[r]-(n) RETURN a, r, n"
    )


if __name__ == "__main__":
    main()
