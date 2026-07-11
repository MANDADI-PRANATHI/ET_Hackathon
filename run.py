"""One-command runner — installs deps, reads your documents, launches the app.

    python run.py            reads whatever REAL documents are in data/corpus/
                              and launches the app. Generates NO fake data. If
                              data/corpus/ is empty, tells you where to add
                              files and stops (nothing to ingest yet).

    python run.py --demo     for TRYING THE PRODUCT ONLY: also generates a
                              full synthetic sample plant (fake work orders,
                              inspections, incidents...) before launching, so
                              every feature has something to show immediately.
                              Never use --demo for real data / a real deployment.

Either way: reads local files, in memory, using plain keyword search — no
extra ML models to download, no Docker, no API key required. For a real
production deployment (Docker, persisted Neo4j, real documents) see the
"Production setup" section in README.md.

Flags:  --port 8000   --no-open   --demo   --full (also install L1/L3 deps,
        use AI extraction during ingestion itself)
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
        print("   installing full pipeline deps (docling, AI extraction)...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
                               "-r", str(ROOT / "requirements-l3.txt")])


def _corpus_has_real_files(corpus_root: pathlib.Path) -> bool:
    skip = {"SOURCES.md", ".gitkeep"}
    return any(p.is_file() and p.name not in skip for p in corpus_root.rglob("*"))


def build_corpus(full: bool, demo: bool) -> bool:
    """Returns True if there's something to serve, False if we should stop."""
    corpus_root = ROOT / "data" / "corpus"

    if demo:
        _step("Generating synthetic sample plant data (--demo: fake data, for trying the product only)")
        import generate_synthetic
        generate_synthetic.main()
    elif not _corpus_has_real_files(corpus_root):
        _step("No documents found")
        print(f"   {corpus_root} is empty — nothing to read yet.\n"
              "   Add your real documents under data/corpus/<folder>/ (work_orders/, "
              "inspections/,\n   incidents/, permits/, regulations/, manuals/, ... — see "
              "docs/ADMIN_GUIDE.md\n   for the full folder list), then run this again.\n\n"
              "   Just want to try the product first? Run:  python run.py --demo")
        return False

    _step("Reading documents and extracting facts")
    from brain.ingest.pipeline import ingest_corpus
    from brain.ontology import load_ontology
    counts = ingest_corpus(corpus_root, ROOT / "data" / "staging",
                           load_ontology(), use_ai=full)
    print(f"   staged {counts['documents']} documents · {counts['nodes']} facts · "
          f"{counts['chunks']} passages")
    return True


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
    ap = argparse.ArgumentParser(description="One-command setup + launch (see --demo for fake sample data)")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-open", action="store_true", help="don't open the browser")
    ap.add_argument("--full", action="store_true",
                    help="also install L1/L3 deps and use AI extraction during ingestion")
    ap.add_argument("--demo", action="store_true",
                    help="generate a fake synthetic sample plant to try the product with "
                         "-- never use this for real data or a real deployment")
    args = ap.parse_args()

    print("Sutradhar — one-command setup + launch")
    ensure_deps(args.full)
    if not build_corpus(args.full, args.demo):
        return
    launch(args.port, open_browser=not args.no_open)


if __name__ == "__main__":
    main()
