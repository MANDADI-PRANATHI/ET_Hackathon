"""Level 2 entry point: merge staged facts into the asset-centric graph.

  make build-graph              merge + metrics + export, and load into Neo4j
  python scripts/build_graph.py [--wipe] [--no-neo4j] [--staging DIR] [--export FILE]

Re-running is the *update* path: MERGE is idempotent, so dropping a new document,
re-ingesting it, and re-running build-graph folds it in without duplicating.
Use --wipe only for a clean rebuild.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from brain.graph.export import graph_json          # noqa: E402
from brain.graph.metrics import graph_stats        # noqa: E402
from brain.graph.model import build_graph          # noqa: E402
from brain.ontology import load_ontology           # noqa: E402
from brain.schema import load_staging              # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Level 2 graph build")
    ap.add_argument("--wipe", action="store_true", help="clear Neo4j before loading")
    ap.add_argument("--no-neo4j", action="store_true", help="skip the Neo4j write")
    ap.add_argument("--staging", default=str(ROOT / "data" / "staging"))
    ap.add_argument("--export", default=str(ROOT / "data" / "graph" / "graph_export.json"))
    ap.add_argument("--metrics", default=str(ROOT / "eval" / "results" / "graph_metrics.json"))
    args = ap.parse_args()

    onto = load_ontology()
    docs = load_staging(pathlib.Path(args.staging))
    if not docs:
        print(f"No staged documents in {args.staging}. Run `make ingest` first.")
        sys.exit(1)

    print(f"Building graph from {len(docs)} staged documents...")
    g = build_graph(docs)
    stats = graph_stats(g)

    print(f"  nodes: {stats['nodes_total']}  edges: {stats['edges_total']}")
    print(f"  by label   : {stats['nodes_by_label']}")
    print(f"  linkage    : score {stats['linkage']['linkage_score']} "
          f"coverage {stats['linkage']['coverage_pct']}")
    if stats["orphans"]:
        print(f"  orphans    : {len(stats['orphans'])} -> {stats['orphans'][:5]}")
    nr = stats["needs_review"]
    if nr["nodes"] or nr["edges"]:
        print(f"  needs review: {nr['nodes']} nodes, {nr['edges']} edges")

    # Always produce the visual export + metrics (works with no database).
    export_path = pathlib.Path(args.export)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(json.dumps(graph_json(g), indent=2), encoding="utf-8")
    print(f"  graph export -> {export_path}")

    metrics_path = pathlib.Path(args.metrics)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    stats_no_peras = {k: v for k, v in stats.items()}
    metrics_path.write_text(json.dumps(stats_no_peras, indent=2), encoding="utf-8")
    print(f"  metrics      -> {metrics_path}")

    if args.no_neo4j:
        print("\nSkipped Neo4j write (--no-neo4j).")
        return

    try:
        from brain.stores.graph_writer import write_graph
        counts = write_graph(g, onto, wipe=args.wipe)
        print(f"\nLoaded into Neo4j: {counts['nodes']} nodes, "
              f"{counts['relationships']} relationships.")
        print("Next: make copilot (Level 3).")
    except Exception as e:  # noqa: BLE001 - keep the artefacts even if the DB is down
        print(f"\n[skip] Neo4j write unavailable ({type(e).__name__}: {e}).")
        print("       Model, metrics, and export were still produced above.")


if __name__ == "__main__":
    main()
