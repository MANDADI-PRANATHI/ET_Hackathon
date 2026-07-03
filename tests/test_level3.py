"""Level 3 regression tests — GraphRAG retrieval + copilot answer assembly.

Pure logic with a stubbed LLM and a tiny staging dir written to tmp_path.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from brain.copilot.answer import Copilot
from brain.ontology import load_ontology
from brain.retrieval.knowledge import KnowledgeBase
from brain.schema import (REGEX, STRUCTURED, Chunk, DocumentRecord, EdgeFact,
                          NodeFact, SourceRef, StagedDoc)

ONTO = load_ontology()


def _staging(tmp_path: Path) -> Path:
    """A small two-document corpus: an asset register + an incident narrative."""
    s = SourceRef(doc_id="reg", path="project_files/asset_register.csv")
    reg = StagedDoc(
        document=DocumentRecord(id="reg", doc_type="ProjectFile",
                                title="Asset Register", path="project_files/asset_register.csv"),
        nodes=[
            NodeFact(label="Asset", key="tag", value="P-101A",
                     properties={"tag": "P-101A", "name": "Crude Feed Pump A",
                                 "asset_class": "Pump"}, source=s, confidence=1.0,
                     extractor=STRUCTURED),
            NodeFact(label="WorkOrder", key="wo_number", value="WO-1",
                     properties={"wo_number": "WO-1", "action": "Seal replacement",
                                 "status": "Completed", "date": "2026-01-02",
                                 "performed_by": "R. Kumar"}, source=s,
                     confidence=1.0, extractor=STRUCTURED),
            NodeFact(label="Person", key="id", value="R. Kumar",
                     properties={"id": "R. Kumar", "name": "R. Kumar"}, source=s,
                     confidence=1.0, extractor=STRUCTURED),
        ],
        edges=[
            EdgeFact(type="MAINTAINS", from_label="WorkOrder", from_value="WO-1",
                     to_label="Asset", to_value="P-101A", source=s, confidence=1.0,
                     extractor=STRUCTURED),
            EdgeFact(type="ABOUT", from_label="Document", from_value="reg",
                     to_label="Asset", to_value="P-101A", source=s, confidence=1.0,
                     extractor=STRUCTURED),
        ],
        chunks=[Chunk(id="reg::c0", doc_id="reg", ordinal=0,
                      text="Asset P-101A Crude Feed Pump A, work order WO-1 seal replacement by R. Kumar.")],
    )
    si = SourceRef(doc_id="inc", path="incidents/inc.txt", page=1,
                   evidence="P-101A tripped due to seal failure from misalignment.")
    inc = StagedDoc(
        document=DocumentRecord(id="inc", doc_type="IncidentReport",
                                title="Incident", path="incidents/inc.txt"),
        nodes=[
            NodeFact(label="Asset", key="tag", value="P-101A",
                     properties={"tag": "P-101A"}, source=si, confidence=0.9, extractor=REGEX),
            NodeFact(label="FailureMode", key="name", value="Seal Failure",
                     properties={"name": "Seal Failure"}, source=si, confidence=0.7, extractor="ai"),
        ],
        edges=[
            EdgeFact(type="AFFECTS", from_label="FailureMode", from_value="Seal Failure",
                     to_label="Asset", to_value="P-101A", source=si, confidence=0.7, extractor="ai"),
            EdgeFact(type="ABOUT", from_label="Document", from_value="inc",
                     to_label="Asset", to_value="P-101A", source=si, confidence=0.9, extractor=REGEX),
        ],
        chunks=[Chunk(id="inc::c0", doc_id="inc", ordinal=0, page=1,
                      text="P-101A tripped due to seal failure from misalignment.")],
    )
    d = tmp_path / "staging"
    reg.write(d)
    inc.write(d)
    return d


class _StubLLM:
    def __init__(self, reply):
        self.reply = reply
        self.seen = {}

    def generate(self, prompt, system=None):
        self.seen = {"prompt": prompt, "system": system}
        return self.reply


def test_spot_assets_tag_name_and_class(tmp_path):
    kb = KnowledgeBase.load(_staging(tmp_path), ONTO)
    assert kb.spot_assets("what about P-101A?") == ["P-101A"]
    assert "P-101A" in kb.spot_assets("history of the crude feed pump a")
    assert "P-101A" in kb.spot_assets("show me all the pumps")   # class synonym


def test_asset_facts_are_cited(tmp_path):
    kb = KnowledgeBase.load(_staging(tmp_path), ONTO)
    facts = kb.asset_facts("P-101A")
    assert facts and all(f.kind == "graph" for f in facts)
    assert any("Seal" in f.statement or "seal" in f.statement for f in facts)
    assert all(f.source.doc_id for f in facts)


def test_retrieve_combines_graph_and_passages(tmp_path):
    kb = KnowledgeBase.load(_staging(tmp_path), ONTO)
    r = kb.retrieve("why did P-101A fail?", top_k=5)
    assert r.assets == ["P-101A"]
    assert r.graph_evidence and r.passage_evidence


def test_answer_has_confidence_and_citations(tmp_path):
    kb = KnowledgeBase.load(_staging(tmp_path), ONTO)
    cop = Copilot(kb, _StubLLM("P-101A failed due to seal failure [1]."))
    a = cop.answer("why did P-101A fail?", role="engineer")
    assert a.assets == ["P-101A"]
    assert a.citations and a.citations[0].n == 1
    assert 0.0 < a.confidence <= 1.0
    assert a.confidence_label in {"Low", "Medium", "High"}
    assert set(a.signals) == {"extraction", "linkage", "retrieval", "agreement", "overall"}


def test_cross_functional_evidence(tmp_path):
    kb = KnowledgeBase.load(_staging(tmp_path), ONTO)
    cop = Copilot(kb, _StubLLM("answer [1]"))
    a = cop.answer("why did P-101A fail?", role="engineer")
    # evidence should span the register (ProjectFile) and the incident (IncidentReport)
    assert {"ProjectFile", "IncidentReport"} <= set(a.source_doc_types)


def test_pii_redaction_by_role(tmp_path):
    kb = KnowledgeBase.load(_staging(tmp_path), ONTO)
    # Technician: not cleared -> name must be hidden in text AND citations
    tech = Copilot(kb, _StubLLM("Work was done by R. Kumar."))
    at = tech.answer("who worked on P-101A?", role="technician")
    assert "R. Kumar" not in at.text
    assert all("R. Kumar" not in c.snippet for c in at.citations)
    # Auditor: cleared -> name may appear
    aud = Copilot(kb, _StubLLM("Work was done by R. Kumar."))
    aa = aud.answer("who worked on P-101A?", role="auditor")
    assert "R. Kumar" in aa.text


def test_no_evidence_is_honest(tmp_path):
    kb = KnowledgeBase.load(_staging(tmp_path), ONTO)
    cop = Copilot(kb, _StubLLM("should not be used"))
    a = cop.answer("what is the capital of France?", role="engineer")
    assert a.confidence == 0.0
    assert "don't have" in a.text.lower() or "insufficient" in a.text.lower()
