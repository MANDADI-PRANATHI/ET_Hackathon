"""Level 4b: run a Root Cause Analysis for an asset.

  python scripts/rca.py P-101B     (or: make rca ASSET=P-101B)
Requires Neo4j up with the graph built, the readings feed (make readings), and an LLM.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from brain.agents.rca import investigate, write_report  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('usage: python scripts/rca.py <ASSET_TAG>   e.g.  P-101B')
        sys.exit(1)
    asset = sys.argv[1].strip()

    result = investigate(asset)
    print(f"\n=== Root Cause Analysis: {asset} ===\n")
    print(result["analysis"])
    path = write_report(result)
    print(f"\nFull report written to: {path}")


if __name__ == "__main__":
    main()
