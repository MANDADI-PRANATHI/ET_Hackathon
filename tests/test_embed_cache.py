"""Regression test: re-ingesting must not silently discard cached embeddings.

This pins the bug found while scaling up the demo corpus — running the
structured-only ingest a second time (e.g. after dropping in a new document)
overwrote every StagedDoc from scratch, wiping out embeddings that had already
been computed and cached by `make embed`. Embeddings for unchanged passages
must survive a re-ingest.
"""
from __future__ import annotations

from pathlib import Path

from brain.ingest.pipeline import ingest_corpus
from brain.ontology import load_ontology
from brain.schema import load_staging

ONTO = load_ontology()


def _write_corpus(corpus: Path) -> None:
    (corpus / "work_orders").mkdir(parents=True)
    (corpus / "work_orders" / "wo.csv").write_text(
        "wo_number,asset_tag,action,date,status,performed_by\n"
        "WO-1,P-101A,Seal replacement,2026-01-02,Completed,R. Kumar\n",
        encoding="utf-8",
    )
    (corpus / "incidents").mkdir(parents=True)
    (corpus / "incidents" / "inc.txt").write_text(
        "P-101A failed due to a seal issue on 2026-01-05.", encoding="utf-8",
    )


def test_reingest_preserves_cached_embeddings(tmp_path):
    corpus = tmp_path / "corpus"
    staging = tmp_path / "staging"
    _write_corpus(corpus)

    ingest_corpus(corpus, staging, ONTO)   # first pass: no embeddings yet
    docs = load_staging(staging)
    chunk_with_text = next(c for d in docs for c in d.chunks if "seal" in c.text.lower())
    chunk_with_text.embedding = [0.1, 0.2, 0.3]   # simulate `make embed` having run
    for d in docs:
        if any(c.id == chunk_with_text.id for c in d.chunks):
            d.write(staging)

    # Re-ingest the same corpus (as if a new document had been dropped in).
    ingest_corpus(corpus, staging, ONTO)

    reloaded = load_staging(staging)
    same_chunk = next(c for d in reloaded for c in d.chunks if c.id == chunk_with_text.id)
    assert same_chunk.embedding == [0.1, 0.2, 0.3]


def test_reingest_does_not_reuse_embedding_if_text_changed(tmp_path):
    corpus = tmp_path / "corpus"
    staging = tmp_path / "staging"
    _write_corpus(corpus)

    ingest_corpus(corpus, staging, ONTO)
    docs = load_staging(staging)
    chunk = next(c for d in docs for c in d.chunks if "seal" in c.text.lower())
    chunk.embedding = [0.1, 0.2, 0.3]
    for d in docs:
        if any(c.id == chunk.id for c in d.chunks):
            d.write(staging)

    # Change the source content so the chunk text (and thus id) differs.
    (corpus / "incidents" / "inc.txt").write_text(
        "A completely different incident narrative about bearing wear.",
        encoding="utf-8",
    )
    ingest_corpus(corpus, staging, ONTO)

    reloaded = load_staging(staging)
    incident_doc = next(d for d in reloaded if d.document.doc_type == "IncidentReport")
    assert all(c.embedding is None for c in incident_doc.chunks)   # not stale-reused
