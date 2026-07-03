"""Level 4c CLI: mine recurring patterns and push proactive warnings.

  make lessons
  python scripts/lessons.py [--date YYYY-MM-DD] [--json]

Combines historical patterns (recurring findings, family clusters, chronic
repeated actions) with live signals (compliance gaps, rising trends) into a
prioritised warning feed. No Neo4j/LLM required.
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from brain.agents.lessons import generate_warnings   # noqa: E402
from brain.graph.model import build_graph             # noqa: E402
from brain.schema import load_staging                 # noqa: E402
from brain.stores.readings import FileReadingsSource  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Level 4c lessons-learned + warnings")
    ap.add_argument("--date")
    ap.add_argument("--staging", default=str(ROOT / "data" / "staging"))
    ap.add_argument("--readings", default=str(ROOT / "data" / "readings" / "readings.csv"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    today = datetime.date.fromisoformat(args.date) if args.date else datetime.date.today()
    g = build_graph(load_staging(pathlib.Path(args.staging)))
    readings = FileReadingsSource(args.readings)
    report = generate_warnings(g, readings=readings, today=today)

    if args.json:
        print(json.dumps({
            "generated_on": report.generated_on,
            "warnings": [vars(w) | {"evidence": [s.path for s in w.evidence]}
                         for w in report.warnings],
            "patterns": [vars(p) | {"evidence": [s.path for s in p.evidence]}
                         for p in report.patterns],
        }, indent=2, default=str))
        return

    md = report.to_markdown()
    print(md)
    out = ROOT / "eval" / "results" / "lessons_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"\nReport written to {out}")


if __name__ == "__main__":
    main()
