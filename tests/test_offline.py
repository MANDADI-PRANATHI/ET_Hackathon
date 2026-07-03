"""Tests for the offline-first fallback: the copilot's extractive answer mode.

When no LLM is configured (or a call fails), the copilot composes a readable,
role-framed answer directly from the cited evidence instead of a "sorry, no
answer" message. This is pure code — no local models, no network, no extra
dependency — so the product's core value never depends on an API being
reachable.
"""
from __future__ import annotations

from pathlib import Path

from brain.copilot.answer import Copilot
from brain.ontology import load_ontology
from brain.retrieval.knowledge import KnowledgeBase
from brain.schema import STRUCTURED, Chunk, DocumentRecord, NodeFact, SourceRef, StagedDoc

ONTO = load_ontology()


def _staging(tmp_path: Path) -> Path:
    s = SourceRef(doc_id="d1", path="p.txt")
    doc = StagedDoc(
        document=DocumentRecord(id="d1", doc_type="IncidentReport", title="t", path="p.txt"),
        nodes=[NodeFact(label="Asset", key="tag", value="P-101A",
                        properties={"tag": "P-101A"}, source=s, confidence=1.0,
                        extractor=STRUCTURED)],
        edges=[],
        chunks=[
            Chunk(id="d1::c0", doc_id="d1", ordinal=0, text="the pump seal failed from misalignment"),
            Chunk(id="d1::c1", doc_id="d1", ordinal=1, text="vibration levels rose before the trip"),
        ],
    )
    d = tmp_path / "staging"
    doc.write(d)
    return d


class _NoLLM:
    def generate(self, *a, **k):
        raise RuntimeError("no cloud/local model reachable")


def test_answer_falls_back_to_extractive_when_llm_none(tmp_path):
    kb = KnowledgeBase.load(_staging(tmp_path), ONTO)
    cop = Copilot(kb, None)   # llm=None entirely
    a = cop.answer("P-101A seal failed misalignment", role="engineer")
    assert a.mode == "extractive"
    assert "[1]" in a.text or "[2]" in a.text          # cites like the generative path would
    assert a.confidence > 0


def test_answer_falls_back_to_extractive_when_llm_errors(tmp_path):
    kb = KnowledgeBase.load(_staging(tmp_path), ONTO)
    cop = Copilot(kb, _NoLLM())
    a = cop.answer("P-101A seal failed misalignment", role="safety_officer")
    assert a.mode == "extractive"
    assert a.text.startswith("From a safety and compliance standpoint")


def test_answer_reports_retrieval_method(tmp_path):
    kb = KnowledgeBase.load(_staging(tmp_path), ONTO)
    cop = Copilot(kb, None)
    a = cop.answer("pump seal failed", role="engineer")
    assert a.retrieval_method == "keyword"
