"""Local answer-faithfulness benchmark — no LLM judge, no API call.

Builds a handful of (answer, evidence) pairs that mimic real copilot output —
some faithful, some drifting — and confirms the local embedding-based scorer
(see brain/copilot/faithfulness.py) tells them apart. This is what lets
"query answer quality" appear on the scorecard without any network dependency.

  python eval/faithfulness_eval.py [--json]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from brain.copilot.faithfulness import score_faithfulness   # noqa: E402
from brain.providers.embeddings import LocalEmbedder        # noqa: E402

CASES = [
    {
        "name": "faithful — paraphrases the evidence",
        "answer": "PSV-110B's statutory inspection is overdue. It was last inspected "
                  "on 2025-11-06, which is well past the six-month regulatory limit.",
        "evidence": [
            "Inspection INSP-207 (Statutory) on asset PSV-110B: result Observation, "
            "last done 2025-11-06.",
            "OISD-STD-105 requires pressure relief valves to be inspected at "
            "intervals not exceeding six months.",
        ],
        "expect_high": True,
    },
    {
        "name": "faithful — direct quote",
        "answer": "Work order WO-4402 replaced the seal on PSV-110B.",
        "evidence": ["Work order WO-4402 on asset PSV-110B: Seal replacement (Completed) "
                     "dated 2026-05-18."],
        "expect_high": True,
    },
    {
        "name": "unfaithful — off-topic hallucination",
        "answer": "Employees should submit expense reports weekly and take lunch "
                  "at noon in the cafeteria.",
        "evidence": ["Asset V-204 (Reflux Drum) is a Vessel by L&T in unit CDU-1, "
                     "criticality High."],
        "expect_high": False,
    },
]


def evaluate() -> dict:
    embedder = LocalEmbedder()
    results = []
    for case in CASES:
        r = score_faithfulness(case["answer"], case["evidence"], embedder)
        correct = (r.score >= 0.55) == case["expect_high"]
        results.append({"name": case["name"], "score": r.score,
                        "expected_high": case["expect_high"], "correct": correct})
    accuracy = round(sum(r["correct"] for r in results) / len(results), 3)
    mean_faithful = round(sum(r["score"] for r in results if r["expected_high"]) /
                         max(1, sum(1 for r in results if r["expected_high"])), 3)
    return {"cases": results, "discrimination_accuracy": accuracy,
            "mean_faithful_score": mean_faithful}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = evaluate()
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print("Local answer-faithfulness benchmark (no LLM judge, no API call)\n")
    for c in result["cases"]:
        mark = "ok" if c["correct"] else "XX"
        print(f"  [{mark}] {c['name']:<40} score={c['score']}")
    print(f"\n  discrimination accuracy: {result['discrimination_accuracy']}")
    print(f"  mean score on faithful answers: {result['mean_faithful_score']}")


if __name__ == "__main__":
    main()
