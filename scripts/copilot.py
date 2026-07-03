"""Level 3 CLI: ask the copilot a question from the terminal.

  make copilot Q="Is PSV-110B overdue for inspection?"
  python scripts/copilot.py --role auditor --question "..." [--embeddings]
  python scripts/copilot.py            # interactive

Runs over the merged graph built from data/staging (no Neo4j required). Needs an
LLM configured (.env) to write the prose answer; without one it still shows the
cited evidence it retrieved.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from brain.copilot.answer import Copilot          # noqa: E402
from brain.copilot.roles import DEFAULT_ROLE, ROLE_FRAMING  # noqa: E402
from brain.ontology import load_ontology           # noqa: E402
from brain.retrieval.knowledge import KnowledgeBase  # noqa: E402


def _print(answer) -> None:
    print(f"\nQ: {answer.question}   [role: {answer.role}]")
    print(f"\n{answer.text}\n")
    print(f"Confidence: {answer.confidence_label} ({answer.confidence}) "
          f"— {answer.signals}")
    if answer.assets:
        print(f"About assets: {', '.join(answer.assets)}")
    if len(answer.source_doc_types) > 1:
        print(f"Cross-functional: evidence spans {', '.join(answer.source_doc_types)}")
    print("Sources:")
    for c in answer.citations[:8]:
        loc = f" p{c.page}" if c.page else ""
        name = pathlib.Path(c.path).name
        print(f"  [{c.n}] ({c.doc_type or c.kind}) {name}{loc}: {c.snippet[:90]}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Level 3 copilot")
    ap.add_argument("--role", default=DEFAULT_ROLE, choices=sorted(ROLE_FRAMING))
    ap.add_argument("--question", "-q")
    ap.add_argument("--staging", default=str(ROOT / "data" / "staging"))
    ap.add_argument("--embeddings", action="store_true",
                    help="use local embeddings for meaning search (else keyword)")
    args = ap.parse_args()

    onto = load_ontology()
    kb = KnowledgeBase.load(args.staging, onto)

    embedder = None
    if args.embeddings:
        from brain.providers.embeddings import LocalEmbedder
        embedder = LocalEmbedder()

    llm = None
    try:
        from brain.providers.llm import get_llm
        llm = get_llm()
    except Exception as e:  # noqa: BLE001
        print(f"[note] No LLM configured ({e}). Showing retrieved evidence only.")

    cop = Copilot(kb, llm, embedder=embedder)

    if args.question:
        _print(cop.answer(args.question, role=args.role))
        return

    print("Copilot ready. Ask a question (blank line to quit).")
    while True:
        try:
            q = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            break
        _print(cop.answer(q, role=args.role))


if __name__ == "__main__":
    main()
