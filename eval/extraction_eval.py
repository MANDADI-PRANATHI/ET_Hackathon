"""Entity-extraction accuracy benchmark (a judged metric).

Runs the deterministic extractor over hand-labelled fixtures and reports
precision / recall / F1 per entity type and overall. Fixtures and labels are
committed under eval/, so this runs anytime with only Level 0 dependencies.

  python eval/extraction_eval.py            # human-readable report
  python eval/extraction_eval.py --json     # machine-readable, for the scorecard
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from brain.ingest.patterns import from_ontology     # noqa: E402
from brain.ontology import load_ontology            # noqa: E402

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
LABELS = pathlib.Path(__file__).resolve().parent / "labels" / "extraction_labels.json"
TYPES = ["equipment_tag", "regulatory_reference", "date"]


def _prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 3), "recall": round(recall, 3),
            "f1": round(f1, 3)}


def evaluate() -> dict:
    onto = load_ontology()
    px = from_ontology(onto)
    labels = json.loads(LABELS.read_text(encoding="utf-8"))

    totals = {t: {"tp": 0, "fp": 0, "fn": 0} for t in TYPES}
    per_fixture = []

    for spec in labels["fixtures"]:
        text = (FIXTURES / spec["file"]).read_text(encoding="utf-8")
        found = px.find_clean(text)
        fx = {"file": spec["file"], "types": {}}
        for t in TYPES:
            got = {m.normalized for m in found.get(t, [])}
            want = set(spec["entities"].get(t, []))
            tp = len(got & want)
            fp = len(got - want)
            fn = len(want - got)
            totals[t]["tp"] += tp
            totals[t]["fp"] += fp
            totals[t]["fn"] += fn
            fx["types"][t] = {"missed": sorted(want - got), "spurious": sorted(got - want)}
        per_fixture.append(fx)

    by_type = {t: _prf(**totals[t]) for t in TYPES}
    agg = {k: sum(totals[t][k] for t in TYPES) for k in ("tp", "fp", "fn")}
    overall = _prf(**agg)
    return {"by_type": by_type, "overall": overall, "per_fixture": per_fixture}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    result = evaluate()
    if args.json:
        print(json.dumps(result, indent=2))
        return

    print("Entity extraction accuracy (deterministic extractor)\n")
    print(f"  {'type':<24}{'precision':>10}{'recall':>9}{'f1':>7}")
    for t, s in result["by_type"].items():
        print(f"  {t:<24}{s['precision']:>10}{s['recall']:>9}{s['f1']:>7}")
    o = result["overall"]
    print(f"  {'-'*50}")
    print(f"  {'OVERALL':<24}{o['precision']:>10}{o['recall']:>9}{o['f1']:>7}")

    misses = [(f['file'], t, d) for f in result['per_fixture']
              for t, d in f['types'].items() if d['missed'] or d['spurious']]
    if misses:
        print("\n  Discrepancies:")
        for file, t, d in misses:
            print(f"    {file} [{t}] missed={d['missed']} spurious={d['spurious']}")
    else:
        print("\n  No discrepancies — extractor matches all labels.")


if __name__ == "__main__":
    main()
