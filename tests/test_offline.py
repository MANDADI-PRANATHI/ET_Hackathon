"""Tests for the offline-first features: local hybrid retrieval, the
extractive answer fallback, and the local faithfulness scorer.

All local models (embedder/reranker) are stubbed here — deliberately, so this
suite stays fast and runs on Level 0 deps, matching the rest of tests/. The
real models are exercised manually (see CLAUDE.md); the logic they plug into
is what's under test.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from brain.copilot.answer import Copilot
from brain.copilot.faithfulness import score_faithfulness, split_sentences
from brain.ontology import load_ontology
from brain.retrieval.knowledge import KnowledgeBase
from brain.schema import STRUCTURED, Chunk, DocumentRecord, EdgeFact, NodeFact, SourceRef, StagedDoc

ONTO = load_ontology()


# --- stubs (no real model downloads; deterministic and fast) ---------------

class StubEmbedder:
    """Maps known strings to hand-picked vectors so cosine similarity is
    predictable; anything unrecognised gets a neutral vector."""

    def __init__(self, vectors: dict):
        self.vectors = vectors

    def embed(self, texts):
        return [self.vectors.get(t, [0.0, 0.0, 1.0]) for t in texts]


class StubReranker:
    """Reverses the input order — deterministic and easy to assert on."""

    def rerank(self, query, docs, top_k=5):
        scored = [(d, float(len(docs) - i)) for i, d in enumerate(docs)]
        return scored[:top_k]


class BrokenReranker:
    def rerank(self, *a, **k):
        raise RuntimeError("model not loaded")


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
            Chunk(id="d1::c1", doc_id="d1", ordinal=1, text="unrelated weather report for the region"),
            Chunk(id="d1::c2", doc_id="d1", ordinal=2, text="vibration levels rose before the trip"),
        ],
    )
    d = tmp_path / "staging"
    doc.write(d)
    return d


# --- Reciprocal Rank Fusion --------------------------------------------------

def test_rrf_fuse_prefers_items_ranked_high_in_multiple_lists():
    fused = KnowledgeBase._rrf_fuse([["a", "b", "c"], ["b", "a", "d"]])
    assert fused["a"] > fused["c"]
    assert fused["b"] > fused["c"]
    assert "d" in fused


# --- hybrid search_passages --------------------------------------------------

def test_search_passages_keyword_only_when_no_embedder(tmp_path):
    kb = KnowledgeBase.load(_staging(tmp_path), ONTO)
    ev = kb.search_passages("pump seal misalignment", top_k=3)
    assert ev
    assert kb._last_retrieval_method == "keyword"


def test_search_passages_uses_dense_when_embeddings_present(tmp_path):
    kb = KnowledgeBase.load(_staging(tmp_path), ONTO)
    # Manually attach embeddings (bypassing a real model) to isolate the dense path.
    target = "the pump seal failed from misalignment"
    for c in kb.chunks:
        c.embedding = [1.0, 0.0, 0.0] if c.text == target else [0.0, 1.0, 0.0]
    embedder = StubEmbedder({"why did the pump fail": [1.0, 0.0, 0.0]})
    ev = kb.search_passages("why did the pump fail", top_k=1, embedder=embedder)
    assert ev[0].statement == target
    assert kb._last_retrieval_method == "hybrid"   # keyword also matched "pump"


def test_ensure_embeddings_backfills_and_is_idempotent(tmp_path):
    kb = KnowledgeBase.load(_staging(tmp_path), ONTO)
    assert all(c.embedding is None for c in kb.chunks)
    embedder = StubEmbedder({})   # neutral vector for everything
    n = kb.ensure_embeddings(embedder)
    assert n == 3
    assert all(c.embedding is not None for c in kb.chunks)
    assert kb.ensure_embeddings(embedder) == 0   # nothing left to backfill


def test_reranker_changes_order_and_is_labelled(tmp_path):
    kb = KnowledgeBase.load(_staging(tmp_path), ONTO)
    for c in kb.chunks:
        c.embedding = [0.1, 0.1, 0.1]
    embedder = StubEmbedder({"q": [0.1, 0.1, 0.1]})
    ev = kb.search_passages("q", top_k=3, embedder=embedder, reranker=StubReranker())
    assert "rerank" in kb._last_retrieval_method
    assert len(ev) <= 3


def test_broken_reranker_falls_back_gracefully(tmp_path):
    kb = KnowledgeBase.load(_staging(tmp_path), ONTO)
    ev = kb.search_passages("pump", top_k=2, reranker=BrokenReranker())
    assert ev   # did not raise; fell back to the fused order


# --- extractive answer fallback ---------------------------------------------

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
    assert a.retrieval_method in {"keyword", "dense", "hybrid", "hybrid+rerank"}


# --- local faithfulness scorer -----------------------------------------------

def test_faithfulness_scores_supported_sentence_high():
    embedder = StubEmbedder({
        "The pump failed due to a seal issue.": [1.0, 0.0],
        "the pump seal failed": [0.99, 0.14],
    })
    result = score_faithfulness("The pump failed due to a seal issue.",
                                ["the pump seal failed"], embedder)
    assert result.score > 0.9
    assert result.n_sentences == 1


def test_faithfulness_scores_unsupported_sentence_low():
    embedder = StubEmbedder({
        "The moon is made of cheese.": [0.0, 1.0],
        "the pump seal failed": [1.0, 0.0],
    })
    result = score_faithfulness("The moon is made of cheese.",
                                ["the pump seal failed"], embedder)
    assert result.score < 0.1


def test_faithfulness_empty_inputs():
    embedder = StubEmbedder({})
    assert score_faithfulness("", ["evidence"], embedder).score == 0.0
    assert score_faithfulness("A real sentence here.", [], embedder).score == 0.0


def test_split_sentences_drops_fragments():
    sents = split_sentences("This is fine. Ok. Also this one works well.")
    assert "This is fine." in sents
    assert "Ok." not in sents   # too short to be a scored claim
