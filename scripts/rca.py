"""Level 4b CLI: root-cause analysis + maintenance recommendations for an asset.

  make rca ASSET=P-101A
  python scripts/rca.py --asset P-101A [--date YYYY-MM-DD] [--json]

Fuses the asset's graph history with recent operating readings (data/readings)
and prints an RCA report. No Neo4j required; an LLM (if configured) writes the
narrative, otherwise a grounded template is used.
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from brain.agents.rca import investigate            # noqa: E402
from brain.graph.model import build_graph            # noqa: E402
from brain.schema import load_staging                # noqa: E402
from brain.stores.readings import FileReadingsSource  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Level 4b RCA agent")
    ap.add_argument("--asset", required=True)
    ap.add_argument("--date", help="assessment date (YYYY-MM-DD); default today")
    ap.add_argument("--staging", default=str(ROOT / "data" / "staging"))
    ap.add_argument("--readings", default=str(ROOT / "data" / "readings" / "readings.csv"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    today = datetime.date.fromisoformat(args.date) if args.date else datetime.date.today()
    g = build_graph(load_staging(pathlib.Path(args.staging)))
    readings = FileReadingsSource(args.readings)

    llm = None
    try:
        from brain.providers.llm import get_llm
        llm = get_llm()
    except Exception:  # noqa: BLE001
        pass

    report = investigate(g, args.asset, readings=readings, today=today, llm=llm)

    if args.json:
        print(json.dumps({
            "asset": report.asset, "assessed_on": report.assessed_on,
            "narrative": report.narrative,
            "findings": [vars(f) | {"evidence": [s.path for s in f.evidence]}
                         for f in report.findings],
            "trends": [vars(t) for t in report.trends],
            "recommendations": [vars(r) for r in report.recommendations],
            "schedule": report.schedule,
        }, indent=2, default=str))
        return

    print(report.to_markdown())
    out = ROOT / "eval" / "results" / f"rca_{report.asset}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.to_markdown(), encoding="utf-8")
    print(f"\nReport written to {out}")


if __name__ == "__main__":
    main()
