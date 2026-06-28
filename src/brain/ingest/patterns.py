"""Deterministic extraction of predictable identifiers (NO AI needed).

Uses the regex patterns declared in the ontology profile to find equipment
tags, regulatory references, and dates in any text.
"""
from __future__ import annotations

import re
from typing import Dict, List

from brain.ontology import load_ontology, patterns as onto_patterns


def find_matches(text: str) -> Dict[str, List[str]]:
    onto = load_ontology()
    out: Dict[str, List[str]] = {}
    for name, pattern in onto_patterns(onto).items():
        found = re.findall(pattern, text)
        # de-dup while preserving order
        seen, uniq = set(), []
        for m in found:
            if m not in seen:
                seen.add(m)
                uniq.append(m)
        out[name] = uniq
    return out
