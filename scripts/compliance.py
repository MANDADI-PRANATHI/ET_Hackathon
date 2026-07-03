"""Level 4a CLI: run the compliance check and print the evidence package.

  make compliance
  python scripts/compliance.py [--date YYYY-MM-DD] [--staging DIR] [--json]

Builds the graph from data/staging, evaluates the regulation ruleset with the
plain-code checker, and prints an audit-ready evidence package plus drafted
non-conformances / CAPAs for any gaps (no Neo4j or LLM required).
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from brain.agents.compliance import run_compliance   # noqa: E402
from brain.graph.model import build_graph             # noqa: E402
from brain.schema import load_staging                 # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Level 4a compliance check")
    ap.add_argument("--date", help="assessment date (YYYY-MM-DD); default today")
    ap.add_argument("--staging", default=str(ROOT / "data" / "staging"))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "eval" / "results" / "compliance_report.md"))
    args = ap.parse_args()

    today = datetime.date.fromisoformat(args.date) if args.date else datetime.date.today()
    g = build_graph(load_staging(pathlib.Path(args.staging)))
    report = run_compliance(g, today=today)

    if args.json:
        print(json.dumps({
            "assessed_on": report.assessed_on, "summary": report.summary,
            "results": [vars(r) | {"evidence": (r.evidence.path if r.evidence else None)}
                        for r in report.results],
            "drafts": report.drafts(),
        }, indent=2, default=str))
        return

    md = report.to_markdown()
    print(md)
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")

    drafts = report.drafts()
    if drafts:
        print("\n## Drafted QMS actions")
        for d in drafts:
            ncr, capa = d["non_conformance"], d["capa"]
            print(f"- {ncr['id']} ({ncr['asset']}): {ncr['finding']}")
            print(f"    -> {capa['id']}: {capa['action']} (due {capa['due_date']})")
    print(f"\nEvidence package written to {out}")


if __name__ == "__main__":
    main()
