"""Entity resolution — deciding when two mentions are the *same* real thing.

This is harder than it looks and we treat it seriously:
  - canonicalise first (tags, regs, names) so obvious variants collapse on merge;
  - never over-merge — "P-101A" and "P-101B" are two backup pumps, not one, so a
    trailing distinguishing suffix keeps them separate;
  - for genuinely unclear cases, *propose* a merge for human confirmation rather
    than silently guessing.

All pure functions — tested without a database.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import List, Tuple

from brain.ingest.patterns import normalize_reg, normalize_tag

_TAG_BASE = re.compile(r"^([A-Za-z]{1,3}-?\d{2,4})([A-Za-z])$")


def normalize_name(value: str) -> str:
    """Collapse whitespace and case for free-text names (failure modes, people)."""
    return re.sub(r"\s+", " ", (value or "").strip()).title()


def canonical_value(label: str, value: str) -> str:
    """The stable identity a node merges on, by label."""
    if label == "Asset":
        return normalize_tag(value)
    if label == "Regulation":
        return normalize_reg(value)
    if label in ("FailureMode", "Person"):
        return normalize_name(value)
    return value


def base_tag(tag: str) -> str:
    """Drop a trailing distinguishing letter: P-101A -> P-101 (the shared family)."""
    m = _TAG_BASE.match(normalize_tag(tag))
    return m.group(1) if m else normalize_tag(tag)


def same_asset(v1: str, v2: str) -> bool:
    """Two asset tags are the same asset only if canonically identical.

    Crucially, P-101A and P-101B share a base family but are NOT the same asset.
    """
    return normalize_tag(v1) == normalize_tag(v2)


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _distinguished_by_suffix(v1: str, v2: str) -> bool:
    """True if the two tags are the same family but different unit (A vs B)."""
    return base_tag(v1) == base_tag(v2) and normalize_tag(v1) != normalize_tag(v2)


def propose_merges(
    label: str, values: List[str], threshold: float = 0.9
) -> List[Tuple[str, str, float]]:
    """Suggest same-entity pairs for HUMAN review — never auto-merge here.

    Skips pairs that are distinguished by an A/B-style suffix, so we don't keep
    proposing to merge the redundant pumps.
    """
    proposals: List[Tuple[str, str, float]] = []
    uniq = sorted(set(values))
    for i in range(len(uniq)):
        for j in range(i + 1, len(uniq)):
            a, b = uniq[i], uniq[j]
            if label == "Asset" and _distinguished_by_suffix(a, b):
                continue
            score = similarity(a, b)
            if score >= threshold:
                proposals.append((a, b, round(score, 3)))
    return proposals
