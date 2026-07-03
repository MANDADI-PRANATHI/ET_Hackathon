"""One-command demo runner — sets up everything and launches the app.

    python run.py

What it does (no Docker, no API key, no heavy ML deps required):
  1. installs the few Python packages it needs (if missing)
  2. generates the sample plant data
  3. reads the documents and extracts facts  (structured + regex path)
  4. starts the API + UI and opens your browser at http://localhost:8000/ui

Everything runs from local files, in memory. The API tries to load local
embeddings + a reranker for hybrid semantic search at startup — if
`sentence-transformers` is already installed it just works; if not, it falls
back to keyword search with no error. Either way, the default sample corpus is
large enough that the API skips auto-embedding at boot (to keep launch fast)
and starts on keyword search — run `python scripts/embed.py` once afterwards
(~2-3 min, one-time, fully local) to cache vectors for instant hybrid search
on every future launch. For the *full* pipeline (real PDFs via Docling, AI
prose extraction, vision drawing reading, Neo4j) see README.md — but this
script is a complete, self-contained working prototype on its own, including
without any cloud API key at all (see "Runs fully offline" in README.md).

Flags:  --port 8000   --no-open   --full (also install L1/L3 deps, use AI
        extraction + embeddings during ingestion itself)
"""
from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys
import threading
import time
import webbrowser

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "scripts"))

# import name -> pip name (the minimal set to run the demo)
MIN_DEPS = {
    "pydantic_settings": "pydantic-settings>=2.0",
    "yaml": "pyyaml>=6.0",
    "fastapi": "fastapi>=0.110",
    "uvicorn": "uvicorn[standard]>=0.29",
}


def _step(msg: str) -> None:
    print(f"\n\033[1m==> {msg}\033[0m" if sys.stdout.isatty() else f"\n==> {msg}")


def ensure_deps(full: bool) -> None:
    _step("Checking dependencies")
    missing = []
    for mod, pkg in MIN_DEPS.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"   installing: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *missing])
    else:
        print("   all present.")
    if full:
        print("   installing full pipeline deps (docling, embeddings)...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
                               "-r", str(ROOT / "requirements-l3.txt")])


def build_corpus(full: bool) -> None:
    _step("Generating sample plant data")
    import generate_synthetic
    generate_synthetic.main()

    _step("Reading documents and extracting facts")
    from brain.ingest.pipeline import ingest_corpus
    from brain.ontology import load_ontology
    counts = ingest_corpus(ROOT / "data" / "corpus", ROOT / "data" / "staging",
                           load_ontology(), use_ai=full, use_embeddings=full)
    print(f"   staged {counts['documents']} documents · {counts['nodes']} facts · "
          f"{counts['chunks']} passages")

    if full:
        _step("Caching passage embeddings for instant hybrid search (local, one-time)")
        import embed
        embed.main()
    else:
        print("   note: run `python scripts/embed.py` once to cache embeddings for "
              "instant hybrid semantic search (keyword search works immediately either way).")


def launch(port: int, open_browser: bool) -> None:
    _step(f"Starting the app on http://localhost:{port}")
    print(f"   UI    : http://localhost:{port}/ui")
    print(f"   API   : http://localhost:{port}/docs")
    print("   (press Ctrl+C to stop)\n")
    os.environ.setdefault("STAGING_DIR", str(ROOT / "data" / "staging"))

    if open_browser:
        def _open():
            time.sleep(2.0)
            try:
                webbrowser.open(f"http://localhost:{port}/ui/")
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()

    import uvicorn
    uvicorn.run("brain.api.app:app", host="127.0.0.1", port=port, log_level="warning")


def main() -> None:
    ap = argparse.ArgumentParser(description="One-command demo runner")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-open", action="store_true", help="don't open the browser")
    ap.add_argument("--full", action="store_true",
                    help="also install L1/L3 deps and use AI + embeddings")
    args = ap.parse_args()

    print("Sutradhar — one-command setup + launch")
    ensure_deps(args.full)
    build_corpus(args.full)
    launch(args.port, open_browser=not args.no_open)


if __name__ == "__main__":
    main()
