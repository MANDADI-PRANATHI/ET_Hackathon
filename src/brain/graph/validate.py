"""Which relationships are legal. A relation is only loaded if its
(from-type, relationship, to-type) shape is declared in the ontology — this
drops the junk the AI sometimes invents (e.g. Document-COMPOSED_OF->Chunk).
"""
from __future__ import annotations

from typing import Any, Dict, Set, Tuple


def allowed_triples(onto: Dict[str, Any]) -> Set[Tuple[str, str, str]]:
    return {(r["from"], r["type"], r["to"]) for r in onto["relationships"]}
