"""Pre-compute and cache passage embeddings — a one-time cost, not a per-launch one.

  make embed
  python scripts/embed.py [--staging DIR]

Computing embeddings for thousands of passages takes real time (CPU inference on
a transformer). Doing it every time the API starts would make every launch slow.
Instead: run this once after ingestion, it embeds every passage that doesn't
already have a vector and writes the result back into data/staging/*.json. From
then on, startup just loads the cached vectors — instant semantic search, still
100% local (no API calls, ever, for this step).

Safe to re-run: only chunks missing an embedding are recomputed, so adding new
documents and re-running this only pays for the new passages.
"""
from __future__ import annotations

import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from brain.schema import load_staging  # noqa: E402


def main() -> None:
    staging = pathlib.Path(sys.argv[sys.argv.index("--staging") + 1]
                           if "--staging" in sys.argv else ROOT / "data" / "staging")
    docs = load_staging(staging)
    if not docs:
        print(f"No staged documents in {staging}. Run `make ingest` first.")
        sys.exit(1)

    todo = [(d, ch) for d in docs for ch in d.chunks if not ch.embedding]
    if not todo:
        total = sum(len(d.chunks) for d in docs)
        print(f"All {total} passages already have cached embeddings. Nothing to do.")
        return

    print(f"Embedding {len(todo)} passages ({len(docs)} documents) — "
          f"first run also downloads the local model (small, one-time)...")
    t0 = time.time()
    from brain.providers.embeddings import LocalEmbedder
    embedder = LocalEmbedder()
    vectors = embedder.embed([ch.text for _d, ch in todo])
    for (_d, ch), vec in zip(todo, vectors):
        ch.embedding = vec
    elapsed = time.time() - t0

    touched = {id(d) for d, _ch in todo}
    for d in docs:
        if id(d) in touched:
            d.write(staging)

    print(f"Done in {elapsed:.1f}s. Cached into {staging} — "
          f"future startups load these instantly (no recompute, no API call).")


if __name__ == "__main__":
    main()
