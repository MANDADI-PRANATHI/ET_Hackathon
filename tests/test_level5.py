"""Level 5 regression tests — scorecard aggregation + ontology-swap generality."""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))

from brain.ontology import load_ontology, node_labels


def test_scorecard_has_all_metrics_and_self_contained_values(monkeypatch):
    import scorecard
    # Stub the embedding-model-backed metric so this test stays on Level 0 deps
    # and fast; faithfulness_eval.py exercises the real local model directly
    # (see `make eval` / eval/faithfulness_eval.py), same pattern as LLM stubs
    # used elsewhere in tests/.
    monkeypatch.setattr(scorecard, "_faithfulness",
                        lambda: {"value": 0.9, "mean_faithful_score": 0.8})
    card = scorecard.build_scorecard()
    expected = {
        "entity_extraction_accuracy", "query_answer_quality",
        "knowledge_graph_linkage_completeness", "compliance_gap_detection",
        "cross_functional_discovery", "rca_quality", "lessons_quality",
        "answer_faithfulness_offline",
    }
    assert expected <= set(card)
    # These benchmarks are self-contained (no staging needed) -> real numbers.
    for key in ("entity_extraction_accuracy", "compliance_gap_detection",
                "rca_quality", "lessons_quality", "answer_faithfulness_offline"):
        val = card[key].get("value")
        assert isinstance(val, (int, float)) and 0.0 <= val <= 1.0


def test_ontology_profiles_are_structurally_interchangeable():
    og = load_ontology("config/ontology/oil_and_gas.yaml")
    mf = load_ontology("config/ontology/manufacturing.yaml")
    # Same node labels and relationship types -> the engine runs unchanged;
    # only the vocabulary (asset classes, tag patterns, regulations) differs.
    assert set(node_labels(og)) == set(node_labels(mf))
    assert {r["type"] for r in og["relationships"]} == {r["type"] for r in mf["relationships"]}
    assert og["hub"] == mf["hub"] == "Asset"
    # But the vocabulary genuinely differs.
    og_classes = next(n for n in og["nodes"] if n["label"] == "Asset")["asset_classes"]
    mf_classes = next(n for n in mf["nodes"] if n["label"] == "Asset")["asset_classes"]
    assert set(og_classes) != set(mf_classes)
