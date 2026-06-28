"""Split document text into overlapping passages and (optionally) embed them
locally with the BGE model so they can be searched by meaning.
"""
from __future__ import annotations

from typing import List

from brain.ingest.models import Chunk


def split_text(text: str, max_chars: int = 1200, overlap: int = 150) -> List[str]:
    text = text.strip()
    if not text:
        return []
    chunks, i = [], 0
    step = max(1, max_chars - overlap)
    while i < len(text):
        chunks.append(text[i:i + max_chars])
        i += step
    return chunks


def embed_chunks(doc_id: str, texts: List[str]) -> List[Chunk]:
    """Embed locally (free, on-device). Imported lazily — needs sentence-transformers."""
    from brain.providers.embeddings import LocalEmbedder

    embedder = LocalEmbedder()
    vectors = embedder.embed(texts)
    return [
        Chunk(id=f"{doc_id}::{i}", text=t, embedding=v)
        for i, (t, v) in enumerate(zip(texts, vectors))
    ]
