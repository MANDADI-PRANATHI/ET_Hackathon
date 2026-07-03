"""Confidence is *built up*, never guessed.

Level 1 stamps a base confidence on every fact according to how it was found
(a number read from a table is more trustworthy than one guessed from prose).
Level 3 later combines these with linkage strength, retrieval-match quality, and
multi-document agreement into the single confidence the user finally sees.
"""
from __future__ import annotations

from typing import Iterable

from brain.schema import AI, REGEX, STRUCTURED, VISION

# Base confidence by extraction method — read a table > match a pattern > read
# prose with AI > read an image with AI (until a human confirms it).
BASE_CONFIDENCE = {
    STRUCTURED: 1.0,
    REGEX: 0.9,
    AI: 0.6,
    VISION: 0.5,
}


def base(extractor: str) -> float:
    return BASE_CONFIDENCE.get(extractor, 0.5)


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def agreement_boost(confidences: Iterable[float]) -> float:
    """Facts confirmed across multiple documents should score higher than any
    single mention. We take the strongest source and add a shrinking bonus for
    each corroborating one, capped at 1.0.

        one source at 0.6            -> 0.60
        two sources at 0.6           -> ~0.72
        three sources at 0.6         -> ~0.79
    """
    vals = sorted((clamp(c) for c in confidences), reverse=True)
    if not vals:
        return 0.0
    score = vals[0]
    for extra in vals[1:]:
        score += (1.0 - score) * extra * 0.5   # diminishing corroboration
    return clamp(score)


def answer_confidence(
    extraction: float,
    linkage: float,
    retrieval: float,
    agreement: float,
    weights: tuple[float, float, float, float] = (0.35, 0.25, 0.25, 0.15),
) -> float:
    """The final, user-facing confidence for a copilot answer (used in Level 3).

    A weighted blend of: how sure extraction was, how solidly the facts are
    linked in the graph, how well retrieved sources matched the question, and
    whether multiple documents agree.
    """
    we, wl, wr, wa = weights
    return clamp(
        we * clamp(extraction)
        + wl * clamp(linkage)
        + wr * clamp(retrieval)
        + wa * clamp(agreement)
    )


def label(confidence: float) -> str:
    """A plain-English band, so weak answers can *say* they're weak."""
    if confidence >= 0.8:
        return "High"
    if confidence >= 0.55:
        return "Medium"
    return "Low"
