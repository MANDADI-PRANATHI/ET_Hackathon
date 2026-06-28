"""Ask the copilot a question from the command line.

  python scripts/ask.py "Is pump P-101B overdue for inspection?"
  make ask Q="What does OSHA require for process safety information?"

Requires Neo4j up with the graph built (make build-graph) and a working LLM.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from brain.copilot.engine import ask  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="+", help="your question")
    ap.add_argument("-k", type=int, default=6, help="passages to retrieve")
    args = ap.parse_args()
    question = " ".join(args.question)

    res = ask(question, k=args.k)
    c = res["confidence"]

    print(f"\nQ: {question}\n")
    print("ANSWER:\n" + res["answer"] + "\n")
    print(f"CONFIDENCE: {c['label']} ({c['score']})  breakdown={c['breakdown']}\n")

    if res["sources"]:
        print("SOURCES:")
        for s in res["sources"]:
            print(f"  [{s['label']}] {s['ref']}: {s['text'][:110]}...")
    if res["facts"]:
        print("\nGRAPH FACTS:")
        for f in res["facts"][:10]:
            print(f"  [{f['label']}] {f['text']}")


if __name__ == "__main__":
    main()
