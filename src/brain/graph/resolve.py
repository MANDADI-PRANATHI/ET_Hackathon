"""Entity resolution for equipment tags — so the same asset written different
ways becomes ONE node.

  "P101", "P 101", "p-101"  -> "P-101"
  "PSV110A"                 -> "PSV-110A"

Deliberately conservative: it normalises spacing/hyphenation and upper-cases,
but does NOT merge across a suffix letter — "P-101A" and "P-101B" stay separate
(they are usually two different backup pumps, not one).
"""
from __future__ import annotations

import re

_TAG = re.compile(r"^([A-Z]{1,3})[\s\-_]?(\d{2,4})([A-Z]?)$")


def canonical_asset_key(key: str) -> str:
    k = (key or "").strip().upper()
    m = _TAG.match(k)
    if m:
        return f"{m.group(1)}-{m.group(2)}{m.group(3)}"
    return k
