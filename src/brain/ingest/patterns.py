"""Deterministic entity extraction — the predictable identifiers, no AI.

Equipment tags (P-101A), regulatory references (OISD-STD-105), and dates follow
strict, well-known shapes, so we match them with regex from the ontology profile.
This is exact, free, and fully auditable — we only fall back to the LLM for facts
buried in prose (see extract.py).

The regex sources live in the ontology YAML (`patterns:`), so swapping industry
profiles swaps the identifier shapes too.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Canonical shape of a reference-designation tag: 1-3 letters, 2-4 digits,
# optional trailing letter (IEC 81346 style). Used for normalisation.
_TAG_SHAPE = re.compile(r"^([A-Za-z]{1,3})-?(\d{2,4})([A-Za-z]?)$")

# Letter prefixes that denote a *document/record* reference, not an equipment
# tag — so "INC-2026", "SOP-021", "WO-4401" don't become bogus assets.
NON_ASSET_PREFIXES = {
    "WO", "NCR", "PTW", "INSP", "CAPA", "INC", "SOP", "REV", "DOC", "REF",
    "ISO", "IEC", "ISA", "CFR", "IS", "OISD", "API", "ANSI", "ASME", "NFPA",
}


def _valid_tag(text: str, start: int, end: int, surface: str) -> bool:
    """Reject tag matches that are really part of a longer document reference.

    Two signals: the match is glued to a hyphen on either side (e.g. the
    "CDU-021" inside "SOP-CDU-021"), or its letter prefix is a known
    document-reference prefix (INC-, WO-, SOP-, ...).
    """
    if start > 0 and text[start - 1] == "-":
        return False
    if end < len(text) and text[end] == "-":
        return False
    m = _TAG_SHAPE.match(surface.strip().upper().replace(" ", ""))
    if m and m.group(1) in NON_ASSET_PREFIXES:
        return False
    return True


@dataclass
class Mention:
    """One entity found in text, with where it sits (for a source citation)."""

    entity_type: str        # equipment_tag | regulatory_reference | date | person
    surface: str            # exactly as written in the text
    normalized: str         # canonical form (P101a -> P-101A)
    start: int
    end: int


def normalize_tag(surface: str) -> str:
    """P101a / p-101-a / PSV110B -> canonical P-101A / PSV-110B."""
    s = surface.strip().upper().replace(" ", "")
    m = _TAG_SHAPE.match(s)
    if not m:
        return s
    letters, digits, suffix = m.groups()
    return f"{letters}-{digits}{suffix}"


def normalize_reg(surface: str) -> str:
    """Collapse whitespace / separators to a stable regulatory code."""
    s = re.sub(r"\s+", " ", surface.strip().upper())
    if s.startswith("OISD"):
        # OISD STD 105 / OISD-105 -> OISD-STD-105 style
        nums = re.findall(r"\d+", s)
        std = "STD-" if "STD" in s else ""
        return f"OISD-{std}{nums[0]}" if nums else s
    return s


def _normalize_date(surface: str) -> str:
    """ISO dates pass through; d/m/y is left as-is (surface kept for citation)."""
    s = surface.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    return s


_NORMALIZERS = {
    "equipment_tag": normalize_tag,
    "regulatory_reference": normalize_reg,
    "date": _normalize_date,
}


class PatternExtractor:
    """Compiles the ontology's regex patterns once and finds mentions in text."""

    def __init__(self, patterns: Dict[str, str]):
        # Case-insensitive for recall; the strict shape (letters + 2-4 digits)
        # keeps false positives away from ordinary words.
        self._compiled = {
            name: re.compile(rx, re.IGNORECASE) for name, rx in patterns.items()
        }

    def find(self, text: str, entity_type: str) -> List[Mention]:
        rx = self._compiled.get(entity_type)
        if not rx:
            return []
        norm = _NORMALIZERS.get(entity_type, lambda x: x.strip())
        seen: List[Mention] = []
        for m in rx.finditer(text):
            surface = m.group(0)
            if entity_type == "equipment_tag" and not _valid_tag(
                text, m.start(), m.end(), surface
            ):
                continue
            seen.append(
                Mention(
                    entity_type=entity_type,
                    surface=surface,
                    normalized=norm(surface),
                    start=m.start(),
                    end=m.end(),
                )
            )
        return seen

    def find_all(self, text: str) -> Dict[str, List[Mention]]:
        return {etype: self.find(text, etype) for etype in self._compiled}

    # More-specific identifiers claim their text first, so an equipment-tag
    # pattern can't match "STD-105" *inside* "OISD-STD-105", etc.
    PRIORITY = ["regulatory_reference", "date", "equipment_tag"]

    def find_clean(self, text: str) -> Dict[str, List[Mention]]:
        """Non-overlapping mentions, resolved by PRIORITY (specific before general)."""
        claimed: List[tuple] = []
        order = [e for e in self.PRIORITY if e in self._compiled]
        order += [e for e in self._compiled if e not in order]
        out: Dict[str, List[Mention]] = {e: [] for e in self._compiled}
        for etype in order:
            for m in self.find(text, etype):
                if any(not (m.end <= s or m.start >= e) for s, e in claimed):
                    continue
                out[etype].append(m)
                claimed.append((m.start, m.end))
        return out


def from_ontology(onto: Dict[str, Any]) -> PatternExtractor:
    from brain.ontology import patterns as _patterns

    return PatternExtractor(_patterns(onto))
