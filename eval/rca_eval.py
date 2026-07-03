"""RCA quality check — does the agent surface the known root cause?

Self-contained, deterministic scenario: an asset with a rising vibration trend
before a trip. We verify the agent ranks the degradation trend as the top cause
and issues a high-urgency recommendation.

  python eval/rca_eval.py [--json]
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
from brain.graph.model import GraphModel             # noqa: E402
from brain.schema import STRUCTURED, SourceRef       # noqa: E402
from brain.stores.readings import ReadingPoint       # noqa: E402

TODAY = datetime.date(2026, 5, 20)
SRC = SourceRef(doc_id="scenario", path="scenario")


class _Readings:
    def parameters(self, asset):
        return ["vibration", "bearing_temp"]

    def series(self, asset, parameter, since=None):
        start = datetime.date(2026, 3, 1)
        vals = ([2.4, 3.1, 4.0, 5.1, 6.3, 7.2] if parameter == "vibration"
                else [58, 59, 60, 60, 61, 61])
        return [ReadingPoint(start + datetime.timedelta(weeks=i), v, "mm/s")
                for i, v in enumerate(vals)]


def evaluate() -> dict:
    g = GraphModel()
    g.add_node("Asset", "tag", "P-101A",
               {"tag": "P-101A", "asset_class": "Pump", "criticality": "High"},
               SRC, 1.0, STRUCTURED)
    report = investigate(g, "P-101A", readings=_Readings(), today=TODAY)

    top = report.findings[0] if report.findings else None
    top_is_condition = bool(top and top.kind == "condition" and "vibration" in top.cause)
    has_high_rec = any(r.urgency == "High" for r in report.recommendations)
    detected_trend = any(t.rising for t in report.trends)
    checks = {"top_cause_is_degradation_trend": top_is_condition,
              "high_urgency_recommendation": has_high_rec,
              "rising_trend_detected": detected_trend,
              "schedule_produced": bool(report.schedule)}
    return {"checks": checks, "score": round(sum(checks.values()) / len(checks), 3),
            "top_finding": (top.cause if top else None)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = evaluate()
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print("RCA quality check\n")
    for k, v in result["checks"].items():
        print(f"  [{'ok' if v else 'XX'}] {k}")
    print(f"\n  score: {result['score']}  (top finding: {result['top_finding']})")


if __name__ == "__main__":
    main()
