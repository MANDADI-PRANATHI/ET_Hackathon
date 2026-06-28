"""Load and validate the ontology profile (the swappable 'vocabulary')."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from brain.config import settings


def load_ontology(path: Optional[str] = None) -> Dict[str, Any]:
    """Read the ontology YAML, validate it, and return it as a dict."""
    p = Path(path or settings.ontology_profile)
    if not p.exists():
        raise FileNotFoundError(f"Ontology profile not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        onto = yaml.safe_load(f)
    _validate(onto)
    return onto


def _validate(onto: Dict[str, Any]) -> None:
    for required in ("profile", "nodes", "relationships"):
        if required not in onto:
            raise ValueError(f"Ontology missing required section: '{required}'")
    labels = {n["label"] for n in onto["nodes"]}
    for rel in onto["relationships"]:
        for side in ("from", "to"):
            if rel[side] not in labels:
                raise ValueError(
                    f"Relationship '{rel['type']}' references unknown node '{rel[side]}'"
                )


def node_labels(onto: Dict[str, Any]) -> List[str]:
    return [n["label"] for n in onto["nodes"]]


def pii_labels(onto: Dict[str, Any]) -> List[str]:
    return onto.get("pii_labels", [])


def patterns(onto: Dict[str, Any]) -> Dict[str, str]:
    """Deterministic regex patterns for predictable identifiers (no AI needed)."""
    return onto.get("patterns", {})
