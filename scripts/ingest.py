"""Level 1 entry point: read the corpus and stage source-stamped facts.

  make ingest              full: structured + regex + AI prose + embeddings
  make ingest-structured   structured + regex only (runs on Level 0 deps)

  python scripts/ingest.py [--structured-only] [--ai] [--embeddings]
                           [--corpus DIR] [--staging DIR] [--path FILE]
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from brain.ontology import load_ontology            # noqa: E402
from brain.ingest.pipeline import ingest_corpus, ingest_file  # noqa: E402
from brain.schema import StagedDoc                  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Level 1 ingestion")
    ap.add_argument("--structured-only", action="store_true",
                    help="skip AI + embeddings (Level 0 deps only)")
    ap.add_argument("--ai", action="store_true", help="force AI prose extraction on")
    ap.add_argument("--embeddings", action="store_true", help="force embeddings on")
    ap.add_argument("--corpus", default=str(ROOT / "data" / "corpus"))
    ap.add_argument("--staging", default=str(ROOT / "data" / "staging"))
    ap.add_argument("--path", help="ingest a single file instead of the whole corpus")
    args = ap.parse_args()

    onto = load_ontology()
    use_ai = args.ai or not args.structured_only
    use_embeddings = args.embeddings or not args.structured_only

    corpus = pathlib.Path(args.corpus)
    staging = pathlib.Path(args.staging)

    mode = "structured-only" if args.structured_only else "full (AI + embeddings)"
    print(f"Level 1 ingestion — mode: {mode}")
    print(f"  corpus : {corpus}")
    print(f"  staging: {staging}\n")

    if args.path:
        llm = None
        embedder = None
        if use_ai:
            from brain.providers.llm import get_llm
            llm = get_llm()
        if use_embeddings:
            from brain.providers.embeddings import LocalEmbedder
            embedder = LocalEmbedder()
        staged = ingest_file(pathlib.Path(args.path), corpus, onto,
                             llm=llm, embedder=embedder)
        if staged is None:
            print("  (unsupported file type — nothing staged)")
            return
        out = staged.write(staging)
        print(f"  staged {out.name}: {len(staged.nodes)} nodes, "
              f"{len(staged.edges)} edges, {len(staged.chunks)} chunks")
        return

    counts = ingest_corpus(corpus, staging, onto,
                           use_ai=use_ai, use_embeddings=use_embeddings)
    print("Done.")
    print(f"  documents staged : {counts['documents']}")
    print(f"  files skipped    : {counts['skipped']}")
    print(f"  nodes / edges    : {counts['nodes']} / {counts['edges']}")
    print(f"  searchable chunks: {counts['chunks']}")
    print(f"\nStaged JSON in {staging}. Next: make build-graph (Level 2).")


if __name__ == "__main__":
    main()
