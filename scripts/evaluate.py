"""Level 5: run the evaluation harness and write reports/scorecard.md.

  python scripts/evaluate.py            (full, with LLM judge)
  python scripts/evaluate.py --no-judge (skip the LLM judge to save calls)
Requires Neo4j up with the graph built, the compliance data, and an LLM.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from brain.eval.scorecard import build_scorecard, write_scorecard  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-judge", action="store_true", help="skip the LLM-as-judge scoring")
    args = ap.parse_args()

    print("Running evaluation (this makes a few model calls)...\n")
    card = build_scorecard(judge=not args.no_judge)

    ec, lk, cp, aq, kb = (card["entity_capture"], card["linkage"], card["compliance"],
                          card["answer_quality"], card["keyword_baseline"])
    print("===== SCORECARD =====")
    print(f"  Entity capture:        {ec['captured']}/{ec['known']} ({ec['recall_pct']}%)")
    print(f"  Linkage completeness:  {lk['linkage_completeness_pct']}%  "
          f"({lk['nodes']} nodes, {lk['relationships']} rels)")
    print(f"  Compliance P/R/F1:     {cp['precision']} / {cp['recall']} / {cp['f1']}")
    print(f"  Answer pass-rate:      {aq['pass_rate_pct']}%")
    print(f"  Answer judge (1-5):    {aq['avg_judge_1to5']}")
    print(f"  Time-to-answer:        {aq['avg_latency_s']} s (direct cited answer)")
    print(f"  Keyword baseline:      {kb['avg_latency_s']} s -> ~{kb['avg_passages_returned']} "
          f"raw passages to read")

    path = write_scorecard(card)
    print(f"\nFull scorecard written to: {path}")


if __name__ == "__main__":
    main()
