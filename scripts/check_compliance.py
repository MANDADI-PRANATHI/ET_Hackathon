"""Level 4a: run the compliance checker and write an audit-ready evidence pack.

  python scripts/check_compliance.py    (or: make compliance)
Requires Neo4j up with the graph built.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from brain.agents.compliance import run_compliance, write_evidence_pack  # noqa: E402

MARK = {"gap": "❌ GAP", "met": "✅ MET", "unknown": "❓ UNK"}


def main() -> None:
    findings = run_compliance()
    gaps = [f for f in findings if f["status"] == "gap"]

    print(f"\nCompliance check: {len(findings)} checks, {len(gaps)} GAP(s)\n")
    for f in findings:
        print(f"  {MARK.get(f['status'], '?')}  {f['asset']:10} [{f['rule_id']}]  {f['detail']}")

    path = write_evidence_pack(findings)
    print(f"\nAudit-ready evidence pack written to: {path}")
    if gaps:
        print(f"Open the report to see the executive summary and corrective actions for {len(gaps)} gap(s).")


if __name__ == "__main__":
    main()
