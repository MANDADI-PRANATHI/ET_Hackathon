"""Copilot benchmark — the Level 3 judged metrics, computed offline.

Without a live LLM we still measure the things that actually decide answer
quality: does retrieval surface the right evidence (groundedness), does it reach
across departments (cross-functional discovery), and does it beat a raw
keyword-only baseline at *locating the answer*?

  python eval/copilot_bench.py            # report
  python eval/copilot_bench.py --json     # for the scorecard
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from brain.ontology import load_ontology            # noqa: E402
from brain.retrieval.knowledge import KnowledgeBase  # noqa: E402
from brain.search.keyword import build_from_staging  # noqa: E402

QUESTIONS = pathlib.Path(__file__).resolve().parent / "benchmark_questions.json"
STAGING = ROOT / "data" / "staging"

DOCTYPE_DEPT = {
    "WorkOrder": "maintenance", "InspectionReport": "quality",
    "QualityRecord": "quality", "Permit": "compliance", "Regulation": "compliance",
    "IncidentReport": "safety", "SOP": "operations",
    "OperatingInstruction": "operations", "ProjectFile": "engineering",
    "PID": "engineering", "Manual": "engineering", "Email": "communications",
}


def _tag_in(text: str, tag: str) -> bool:
    t = text.lower()
    return tag.lower() in t or tag.lower().replace("-", "") in t.replace("-", "")


def evaluate() -> dict:
    onto = load_ontology()
    kb = KnowledgeBase.load(STAGING, onto)
    kw = build_from_staging(STAGING)
    specs = json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"]

    rows = []
    for s in specs:
        t0 = time.perf_counter()
        r = kb.retrieve(s["q"], top_k=5)
        graph_ms = (time.perf_counter() - t0) * 1000.0

        cites = r.all
        got_assets = set(r.assets)
        want_assets = set(s.get("expect_assets", []))
        asset_hit = want_assets <= got_assets

        got_doc_types = {e.doc_type for e in cites if e.doc_type}
        want_doc_types = set(s.get("expect_doc_types", []))
        doc_type_hit = bool(want_doc_types & got_doc_types)

        blob = " ".join((e.statement + " " + (e.source.evidence or "")) for e in cites).lower()
        terms = s.get("expect_terms", [])
        term_frac = (sum(1 for t in terms if t.lower() in blob) / len(terms)) if terms else 1.0

        grounded = asset_hit and doc_type_hit and term_frac >= 0.5

        depts = {DOCTYPE_DEPT.get(dt, "other") for dt in got_doc_types}
        cross_functional = any(d != s.get("origin") for d in depts) and len(depts) >= 1

        # keyword baseline: does its top hit even reach the right asset?
        t1 = time.perf_counter()
        hits, _ = kw.search(s["q"], top_k=1)
        kw_ms = (time.perf_counter() - t1) * 1000.0
        kw_asset_ok = bool(hits and want_assets and
                           any(_tag_in(hits[0].text, a) for a in want_assets))
        graph_asset_ok = asset_hit

        rows.append({
            "q": s["q"], "asset_hit": asset_hit, "doc_type_hit": doc_type_hit,
            "term_frac": round(term_frac, 2), "grounded": grounded,
            "cross_functional": cross_functional,
            "graph_ms": round(graph_ms, 2), "kw_ms": round(kw_ms, 2),
            "kw_top1_reaches_asset": kw_asset_ok, "graph_reaches_asset": graph_asset_ok,
            "doc_types": sorted(got_doc_types),
        })

    n = len(rows)
    agg = {
        "questions": n,
        "asset_spotting": round(sum(r["asset_hit"] for r in rows) / n, 3),
        "doc_type_coverage": round(sum(r["doc_type_hit"] for r in rows) / n, 3),
        "term_coverage": round(sum(r["term_frac"] for r in rows) / n, 3),
        "groundedness": round(sum(r["grounded"] for r in rows) / n, 3),
        "cross_functional_rate": round(sum(r["cross_functional"] for r in rows) / n, 3),
        "keyword_top1_asset_accuracy": round(sum(r["kw_top1_reaches_asset"] for r in rows) / n, 3),
        "graphrag_asset_accuracy": round(sum(r["graph_reaches_asset"] for r in rows) / n, 3),
        "mean_graph_ms": round(sum(r["graph_ms"] for r in rows) / n, 2),
        "mean_keyword_ms": round(sum(r["kw_ms"] for r in rows) / n, 2),
    }
    return {"aggregate": agg, "per_question": rows}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = evaluate()
    if args.json:
        print(json.dumps(result, indent=2))
        return

    a = result["aggregate"]
    print("Copilot benchmark (retrieval-grounded, offline)\n")
    print(f"  questions                    : {a['questions']}")
    print(f"  asset spotting               : {a['asset_spotting']}")
    print(f"  doc-type coverage            : {a['doc_type_coverage']}")
    print(f"  term coverage                : {a['term_coverage']}")
    print(f"  groundedness (all-of)        : {a['groundedness']}")
    print(f"  cross-functional discovery   : {a['cross_functional_rate']}")
    print(f"  asset-locating accuracy      : GraphRAG {a['graphrag_asset_accuracy']} "
          f"vs keyword {a['keyword_top1_asset_accuracy']}")
    print(f"  retrieval latency (ms)       : GraphRAG {a['mean_graph_ms']} "
          f"vs keyword {a['mean_keyword_ms']}")

    print("\n  Per question:")
    for r in result["per_question"]:
        flag = "x-fn" if r["cross_functional"] else "    "
        print(f"    [{flag}] grounded={int(r['grounded'])} "
              f"assets={int(r['asset_hit'])} terms={r['term_frac']} :: {r['q'][:56]}")


if __name__ == "__main__":
    main()
