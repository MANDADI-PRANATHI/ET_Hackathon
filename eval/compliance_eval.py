"""Compliance gap-detection accuracy (a judged metric).

Self-contained and deterministic: we build a small scenario with known-correct
statuses and check the plain-code evaluator against them. Treating GAP as the
positive class, we report precision / recall / F1 for gap detection.

  python eval/compliance_eval.py [--json]
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from brain.agents.compliance import GAP, run_compliance   # noqa: E402
from brain.graph.model import GraphModel                  # noqa: E402
from brain.schema import STRUCTURED, SourceRef            # noqa: E402

ASSESS = datetime.date(2026, 7, 3)

# (asset, class, last_inspection_date or None, expected_status)
SCENARIO = [
    ("PSV-110A", "Valve", "2026-04-23", "MET"),
    ("PSV-110B", "Valve", "2025-11-06", "GAP"),      # the planted overdue valve
    ("PSV-200", "Valve", None, "UNKNOWN"),           # no record
    ("V-204", "Vessel", "2026-01-19", "MET"),
    ("V-900", "Vessel", "2024-01-01", "GAP"),        # >365 days
]


def _scenario_graph() -> GraphModel:
    g = GraphModel()
    src = SourceRef(doc_id="scenario", path="scenario.csv")
    for i, (tag, cls, last, _exp) in enumerate(SCENARIO):
        g.add_node("Asset", "tag", tag, {"tag": tag, "asset_class": cls}, src, 1.0, STRUCTURED)
        if last:
            iid = f"INSP-{i}"
            g.add_node("Inspection", "inspection_id", iid,
                       {"inspection_id": iid, "type": "Statutory", "last_inspection_date": last},
                       src, 1.0, STRUCTURED)
            g.add_edge("INSPECTS", "Inspection", iid, "Asset", tag, src, 1.0, STRUCTURED)
    return g


def evaluate() -> dict:
    g = _scenario_graph()
    report = run_compliance(g, today=ASSESS)
    got = {r.asset: r.status for r in report.results}
    expected = {tag: exp for tag, _c, _l, exp in SCENARIO}

    tp = fp = fn = 0
    correct = 0
    for tag, exp in expected.items():
        g_status = got.get(tag)
        correct += int(g_status == exp)
        if exp == GAP and g_status == GAP:
            tp += 1
        elif g_status == GAP and exp != GAP:
            fp += 1
        elif exp == GAP and g_status != GAP:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "assessed_on": ASSESS.isoformat(),
        "status_accuracy": round(correct / len(expected), 3),
        "gap_detection": {"tp": tp, "fp": fp, "fn": fn,
                          "precision": round(precision, 3), "recall": round(recall, 3),
                          "f1": round(f1, 3)},
        "detail": {tag: {"expected": expected[tag], "got": got.get(tag)} for tag in expected},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = evaluate()
    if args.json:
        print(json.dumps(result, indent=2))
        return
    gd = result["gap_detection"]
    print("Compliance gap-detection accuracy\n")
    print(f"  status accuracy (all)  : {result['status_accuracy']}")
    print(f"  gap precision/recall/f1: {gd['precision']} / {gd['recall']} / {gd['f1']}")
    for tag, d in result["detail"].items():
        mark = "ok" if d["expected"] == d["got"] else "XX"
        print(f"    [{mark}] {tag:10} expected={d['expected']:8} got={d['got']}")


if __name__ == "__main__":
    main()
