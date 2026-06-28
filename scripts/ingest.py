"""Run the Level 1 ingestion pipeline over the corpus.

  python scripts/ingest.py                     # full: AI + embeddings (needs Gemini key + L1 deps)
  python scripts/ingest.py --structured-only   # no AI / no embeddings (runs with just L0 deps)
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from brain.ingest.pipeline import run  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="data/corpus")
    ap.add_argument("--staging", default="data/staging")
    ap.add_argument("--structured-only", action="store_true",
                    help="skip AI + embeddings (no API key / heavy deps needed)")
    args = ap.parse_args()
    run(args.corpus, args.staging,
        use_ai=not args.structured_only,
        use_embeddings=not args.structured_only)


if __name__ == "__main__":
    main()
