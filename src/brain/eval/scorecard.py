"""Compute the judge-facing metrics:
  - entity capture (did we get the known assets into the graph)
  - knowledge-graph linkage completeness
  - compliance gap-detection precision/recall/F1 vs ground truth
  - answer quality on the expert benchmark (key-fact pass rate + LLM-judge 1-5)
  - time-to-answer (copilot) vs a keyword-search baseline
"""
from __future__ import annotations

import pathlib
import re
import statistics
import time
from typing import Any, Dict, List

import yaml
from neo4j import GraphDatabase

from brain.agents.compliance import run_compliance
from brain.config import settings
from brain.copilot.engine import ask


def _driver():
    return GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))


def load_benchmark(path: str = "eval/benchmark.yaml") -> Dict[str, Any]:
    return yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))


def entity_capture(known: List[str]) -> Dict[str, Any]:
    d = _driver()
    with d.session() as s:
        found = set(s.run("MATCH (a:Asset) RETURN collect(a.tag) AS t").single()["t"])
    d.close()
    captured = [k for k in known if k in found]
    missing = [k for k in known if k not in found]
    return {"known": len(known), "captured": len(captured),
            "recall_pct": round(100 * len(captured) / len(known), 1) if known else 0.0,
            "missing": missing}


def linkage() -> Dict[str, Any]:
    d = _driver()
    with d.session() as s:
        total = s.run("MATCH (n) WHERE NOT n:Chunk AND NOT n:Document RETURN count(n) AS c").single()["c"]
        linked = s.run("MATCH (n) WHERE NOT n:Chunk AND NOT n:Document AND (n)--() "
                       "RETURN count(n) AS c").single()["c"]
        nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
    d.close()
    pct = round(100 * linked / total, 1) if total else 0.0
    return {"linkage_completeness_pct": pct, "nodes": nodes, "relationships": rels}


def compliance_metrics(gt_gaps: List[str]) -> Dict[str, Any]:
    findings = run_compliance()
    pred = {f["asset"] for f in findings if f["status"] == "gap"}
    gt = set(gt_gaps)
    tp, fp, fn = len(pred & gt), len(pred - gt), len(gt - pred)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"predicted_gaps": sorted(pred), "ground_truth": sorted(gt),
            "precision": round(precision, 2), "recall": round(recall, 2), "f1": round(f1, 2)}


def _contains(text: str, needles: List[str]) -> List[str]:
    low = (text or "").lower()
    return [n for n in needles if n.lower() in low]


def _llm_judge(question: str, answer: str, sources, facts) -> int:
    from brain.providers.llm import get_llm
    ctx = " | ".join(s["text"][:140] for s in sources[:3])
    ctx += " | " + " ".join(f["text"] for f in facts[:6])
    out = get_llm().generate(
        f"Rate 1-5 how correct and well-grounded the ANSWER is given the CONTEXT. "
        f"Reply with ONLY one integer 1-5.\nQUESTION: {question}\nANSWER: {answer}\nCONTEXT: {ctx[:1500]}",
        system="You are a strict evaluator. Output only a single integer 1-5.")
    m = re.search(r"[1-5]", out or "")
    return int(m.group(0)) if m else 0


def answer_quality(qa: List[Dict[str, Any]], judge: bool = True) -> Dict[str, Any]:
    try:
        ask("warm up the pipeline")  # warm the embedder so latencies are steady-state
    except Exception:  # noqa: BLE001
        pass
    results, latencies, judges = [], [], []
    for item in qa:
        q = item["question"]
        try:
            t0 = time.time()
            res = ask(q)
            dt = time.time() - t0
        except Exception as e:  # noqa: BLE001 - keep the run going on a transient failure
            results.append({"q": q, "passed": False, "latency_s": None,
                            "judge": None, "missing": [f"ERROR: {e}"]})
            continue
        latencies.append(dt)
        ans = res["answer"]
        must = item.get("must_include", [])
        any_ = item.get("must_include_any", [])
        hit_must = _contains(ans, must)
        must_ok = len(hit_must) == len(must)
        any_ok = (not any_) or bool(_contains(ans, any_))
        passed = must_ok and any_ok
        score = None
        if judge:
            try:
                score = _llm_judge(q, ans, res["sources"], res["facts"])
            except Exception:  # noqa: BLE001
                score = None
        if score:
            judges.append(score)
        results.append({"q": q, "passed": passed, "latency_s": round(dt, 2),
                        "judge": score, "missing": [m for m in must if m not in hit_must]})
    return {"results": results,
            "pass_rate_pct": round(100 * sum(r["passed"] for r in results) / len(results), 1) if results else 0.0,
            "avg_latency_s": round(statistics.mean(latencies), 2) if latencies else None,
            "avg_judge_1to5": round(statistics.mean(judges), 2) if judges else None}


def keyword_baseline(qa: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Traditional search: substring match over passages — fast, but returns raw
    passages a human must read, not an answer."""
    d = _driver()
    lat, matches = [], []
    with d.session() as s:
        for item in qa:
            words = [w for w in re.findall(r"[A-Za-z0-9-]+", item["question"]) if len(w) > 4]
            kw = max(words, key=len) if words else item["question"][:6]
            t0 = time.time()
            n = s.run("MATCH (c:Chunk) WHERE toLower(c.text) CONTAINS toLower($kw) "
                      "RETURN count(c) AS n", kw=kw).single()["n"]
            lat.append(time.time() - t0)
            matches.append(n)
    d.close()
    return {"avg_latency_s": round(statistics.mean(lat), 3),
            "avg_passages_returned": round(statistics.mean(matches), 1)}


def build_scorecard(benchmark_path: str = "eval/benchmark.yaml", judge: bool = True) -> Dict[str, Any]:
    bm = load_benchmark(benchmark_path)
    return {
        "entity_capture": entity_capture(bm["known_assets"]),
        "linkage": linkage(),
        "compliance": compliance_metrics(bm["compliance_gaps"]),
        "answer_quality": answer_quality(bm["qa"], judge=judge),
        "keyword_baseline": keyword_baseline(bm["qa"]),
    }


def write_scorecard(card: Dict[str, Any], path: str = "reports/scorecard.md") -> pathlib.Path:
    ec, lk, cp, aq, kb = (card["entity_capture"], card["linkage"], card["compliance"],
                          card["answer_quality"], card["keyword_baseline"])
    L = ["# Evaluation Scorecard", "",
         "| Metric | Result |", "|---|---|",
         f"| Entity capture (known assets) | {ec['captured']}/{ec['known']} ({ec['recall_pct']}%) |",
         f"| Knowledge-graph linkage completeness | {lk['linkage_completeness_pct']}% "
         f"({lk['nodes']} nodes, {lk['relationships']} relationships) |",
         f"| Compliance gap detection (P / R / F1) | {cp['precision']} / {cp['recall']} / {cp['f1']} |",
         f"| Answer quality — key-fact pass rate | {aq['pass_rate_pct']}% |",
         f"| Answer quality — LLM judge (1-5) | {aq['avg_judge_1to5']} |",
         f"| Time-to-answer (copilot, direct cited answer) | {aq['avg_latency_s']} s |",
         f"| Keyword search baseline | {kb['avg_latency_s']} s, but returns "
         f"~{kb['avg_passages_returned']} raw passages to read (no answer) |",
         "",
         "## Compliance detail",
         f"- Predicted gaps: {cp['predicted_gaps']}",
         f"- Ground truth: {cp['ground_truth']}",
         ""]
    if ec["missing"]:
        L.append(f"_Entities not captured: {ec['missing']}_\n")
    L.append("## Per-question results")
    for r in aq["results"]:
        mark = "PASS" if r["passed"] else "FAIL"
        miss = f" (missing: {r['missing']})" if r["missing"] else ""
        L.append(f"- [{mark}] {r['q']}  — {r['latency_s']}s, judge={r['judge']}{miss}")
    out = pathlib.Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L), encoding="utf-8")
    return out
