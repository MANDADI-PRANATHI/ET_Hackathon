"""The scorecard — every judged metric in one place, computed live.

Runs each benchmark and maps the results straight onto the problem statement's
evaluation focus, so a judge sees the number generated, not just claimed. Each
metric degrades gracefully (marked "n/a") if its inputs aren't present yet.

  make scorecard
  python eval/scorecard.py [--json]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

STAGING = ROOT / "data" / "staging"


def _safe(fn, default=None):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 - a missing input must not break the scorecard
        return {"error": f"{type(e).__name__}: {e}", "value": default}


def _extraction():
    import extraction_eval
    r = extraction_eval.evaluate()
    return {"value": r["overall"]["f1"], "detail": r["overall"]}


def _copilot():
    import copilot_bench
    a = copilot_bench.evaluate()["aggregate"]
    return {"groundedness": a["groundedness"],
            "cross_functional_rate": a["cross_functional_rate"],
            "asset_spotting": a["asset_spotting"],
            "graph_ms": a["mean_graph_ms"], "keyword_ms": a["mean_keyword_ms"]}


def _linkage():
    from brain.graph.metrics import linkage_completeness
    from brain.graph.model import build_graph
    from brain.schema import load_staging
    g = build_graph(load_staging(STAGING))
    link = linkage_completeness(g)
    return {"value": link["linkage_score"], "coverage": link["coverage_pct"],
            "assets": link["assets"]}


def _compliance():
    import compliance_eval
    r = compliance_eval.evaluate()
    return {"value": r["gap_detection"]["f1"], "detail": r["gap_detection"]}


def _rca():
    import rca_eval
    return {"value": rca_eval.evaluate()["score"]}


def _lessons():
    import lessons_eval
    return {"value": lessons_eval.evaluate()["score"]}


def _faithfulness():
    import faithfulness_eval
    r = faithfulness_eval.evaluate()
    return {"value": r["discrimination_accuracy"], "mean_faithful_score": r["mean_faithful_score"]}


def build_scorecard() -> dict:
    return {
        "entity_extraction_accuracy": _safe(_extraction),
        "query_answer_quality": _safe(_copilot),
        "knowledge_graph_linkage_completeness": _safe(_linkage),
        "compliance_gap_detection": _safe(_compliance),
        "cross_functional_discovery": _safe(
            lambda: {"value": _copilot()["cross_functional_rate"]}),
        "rca_quality": _safe(_rca),
        "lessons_quality": _safe(_lessons),
        # Computed entirely by the local embedding model — zero API calls, so
        # this number is reproducible even with no internet connection at all.
        "answer_faithfulness_offline": _safe(_faithfulness),
    }


def _fmt(v) -> str:
    if isinstance(v, dict):
        if "error" in v:
            return "n/a"
        for k in ("value", "groundedness"):
            if k in v:
                return str(v[k])
    return str(v)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "eval" / "results" / "scorecard.json"))
    args = ap.parse_args()

    card = build_scorecard()
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(card, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(card, indent=2))
        return

    print("=" * 60)
    print(" SUTRADHAR — SCORECARD (maps to the evaluation focus)")
    print("=" * 60)
    rows = [
        ("Entity extraction accuracy (F1)", _fmt(card["entity_extraction_accuracy"])),
        ("Query answer quality (groundedness)", _fmt(card["query_answer_quality"])),
        ("Knowledge-graph linkage completeness", _fmt(card["knowledge_graph_linkage_completeness"])),
        ("Compliance-gap detection (F1)", _fmt(card["compliance_gap_detection"])),
        ("Cross-functional discovery rate", _fmt(card["cross_functional_discovery"])),
        ("RCA quality", _fmt(card["rca_quality"])),
        ("Lessons-learned quality", _fmt(card["lessons_quality"])),
        ("Answer faithfulness (offline, no API)", _fmt(card["answer_faithfulness_offline"])),
    ]
    for name, val in rows:
        print(f"  {name:<42}{val:>12}")

    cp = card["query_answer_quality"]
    if isinstance(cp, dict) and "graph_ms" in cp:
        print(f"\n  Time-to-answer: GraphRAG {cp['graph_ms']} ms vs "
              f"keyword {cp['keyword_ms']} ms")
    print(f"\n  Written to {out}")


if __name__ == "__main__":
    main()
