"""Level 1 regression tests — the pure extraction/ingestion logic.

These run with only Level 0 dependencies (no Neo4j, no LLM, no docling).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from brain.ingest import extract as ax
from brain.ingest.chunk import chunk_text
from brain.ingest.confidence import agreement_boost, answer_confidence, base, label
from brain.ingest.patterns import PatternExtractor, normalize_tag, normalize_reg
from brain.ingest.pipeline import ingest_file
from brain.ingest.readers.structured import read_structured
from brain.ontology import load_ontology
from brain.schema import AI, REGEX, STRUCTURED, SourceRef

ONTO = load_ontology()
PATTERNS = ONTO["patterns"]


# --- deterministic pattern extraction --------------------------------------

def test_normalize_tag_variants():
    assert normalize_tag("p101a") == "P-101A"
    assert normalize_tag("PSV110B") == "PSV-110B"
    assert normalize_tag("V-204") == "V-204"
    assert normalize_tag("psv 110 b".replace(" ", "")) == "PSV-110B"


def test_normalize_reg():
    assert normalize_reg("OISD STD 105") == "OISD-STD-105"
    assert normalize_reg("OISD-105") == "OISD-105"


def test_tag_rejects_document_references():
    px = PatternExtractor(PATTERNS)
    tags = {m.normalized for m in px.find("Ref INC-2026-014 and SOP-CDU-021 here", "equipment_tag")}
    assert tags == set()          # both are document references, not assets


def test_reg_ref_not_matched_as_tag():
    px = PatternExtractor(PATTERNS)
    found = px.find_clean("Per OISD-STD-105 the valve PSV-110B was checked.")
    tags = {m.normalized for m in found["equipment_tag"]}
    regs = {m.normalized for m in found["regulatory_reference"]}
    assert tags == {"PSV-110B"}   # 'STD-105' inside the reg ref is not a tag
    assert regs == {"OISD-STD-105"}


def test_find_clean_no_overlaps():
    px = PatternExtractor(PATTERNS)
    found = px.find_clean("On 2026-05-18 pump p-101a tripped near PSV110B.")
    assert {m.normalized for m in found["equipment_tag"]} == {"P-101A", "PSV-110B"}
    assert {m.normalized for m in found["date"]} == {"2026-05-18"}


# --- chunking ---------------------------------------------------------------

def test_chunking_splits_and_covers():
    text = "\n\n".join(f"Paragraph {i} about the plant." for i in range(20))
    chunks = chunk_text("doc", text, target_chars=200, overlap_chars=40)
    assert len(chunks) > 1
    assert all(c.doc_id == "doc" for c in chunks)
    assert all(c.text.strip() for c in chunks)
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_chunking_empty():
    assert chunk_text("doc", "") == []
    assert chunk_text("doc", "   \n\n  ") == []


# --- confidence -------------------------------------------------------------

def test_confidence_bases_ordered():
    assert base(STRUCTURED) > base(REGEX) > base(AI) > 0


def test_agreement_boost_monotonic():
    one = agreement_boost([0.6])
    two = agreement_boost([0.6, 0.6])
    three = agreement_boost([0.6, 0.6, 0.6])
    assert one < two < three <= 1.0


def test_answer_confidence_and_label():
    hi = answer_confidence(1.0, 1.0, 1.0, 1.0)
    lo = answer_confidence(0.2, 0.1, 0.1, 0.0)
    assert hi > lo
    assert label(hi) == "High" and label(lo) == "Low"


# --- structured reading -----------------------------------------------------

def test_read_structured_work_orders(tmp_path):
    csv = tmp_path / "wo.csv"
    csv.write_text(
        "wo_number,asset_tag,action,date,status,performed_by\n"
        "WO-1,P-101A,Seal replacement,2026-01-02,Completed,R. Kumar\n",
        encoding="utf-8",
    )
    res = read_structured(csv, "wo-doc")
    labels = {n.label for n in res.nodes}
    assert {"WorkOrder", "Asset", "Person"} <= labels
    assert any(e.type == "MAINTAINS" for e in res.edges)
    assert any(e.type == "PERFORMED" for e in res.edges)
    assert all(n.extractor == STRUCTURED and n.confidence == 1.0 for n in res.nodes)
    assert res.row_texts and "WO-1" in res.row_texts[0]


# --- AI prose extraction (stubbed LLM) --------------------------------------

class _StubLLM:
    def __init__(self, reply: str):
        self._reply = reply

    def generate(self, prompt: str, system=None) -> str:
        return self._reply


def test_ai_extract_maps_to_ontology():
    reply = ('[{"subject":"P-101A","subject_type":"Asset","relation":"AFFECTS",'
             '"object":"Seal failure","object_type":"FailureMode",'
             '"evidence":"seal failed on P-101A","confidence":0.7}]')
    src = SourceRef(doc_id="d", path="p.txt")
    nodes, edges = ax.extract_prose_facts("seal failed on P-101A", src, ONTO, _StubLLM(reply))
    assert {n.label for n in nodes} == {"Asset", "FailureMode"}
    assert edges[0].type == "AFFECTS"
    assert edges[0].from_label == "FailureMode" and edges[0].to_label == "Asset"
    assert all(n.extractor == AI and n.confidence <= 0.85 for n in nodes)


def test_ai_extract_rejects_unknown_types_and_bad_json():
    src = SourceRef(doc_id="d", path="p.txt")
    bad = ('[{"subject":"x","subject_type":"Alien","relation":"ZAPS",'
           '"object":"y","object_type":"Asset","evidence":"e"}]')
    assert ax.extract_prose_facts("t", src, ONTO, _StubLLM(bad)) == ([], [])
    assert ax.extract_prose_facts("t", src, ONTO, _StubLLM("not json")) == ([], [])
    assert ax.extract_prose_facts("t", src, ONTO, None) == ([], [])


# --- full file ingestion (text path, no external services) ------------------

def test_ingest_text_file(tmp_path):
    corpus = tmp_path / "corpus"
    (corpus / "incidents").mkdir(parents=True)
    f = corpus / "incidents" / "inc.txt"
    f.write_text(
        "Pump P-101A failed per OISD-STD-105 on 2026-05-18.\n\n"
        "Standby P-101B started; PSV-110B inspection overdue.",
        encoding="utf-8",
    )
    staged = ingest_file(f, corpus, ONTO)
    assert staged is not None
    assert staged.document.doc_type == "IncidentReport"
    assets = {n.value for n in staged.nodes if n.label == "Asset"}
    assert {"P-101A", "P-101B", "PSV-110B"} <= assets
    assert any(n.label == "Regulation" and n.value == "OISD-STD-105" for n in staged.nodes)
    assert any(e.type == "MENTIONS" for e in staged.edges)
    assert any(e.type == "ABOUT" for e in staged.edges)
    assert staged.chunks and all(c.embedding is None for c in staged.chunks)


def test_ingest_skips_unsupported(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    weird = corpus / "thing.xyz"
    weird.write_text("data", encoding="utf-8")
    assert ingest_file(weird, corpus, ONTO) is None
