"""Local, free 'understands-meaning' models — embeddings + reranker.

Used from Level 1 onward. Runs on-device (no API calls, no cost). The
sentence-transformers dependency is installed with the Level 1 requirements;
imports are lazy so Level 0 doesn't need it.
"""
from __future__ import annotations

from typing import List, Tuple

from brain.config import settings


class LocalEmbedder:
    """Turns text into 'meaning fingerprints' (vectors) for search by meaning."""

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(settings.embed_model)

    def embed(self, texts: List[str]) -> List[List[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]


class LocalReranker:
    """Re-orders retrieved passages by how well they answer the question."""

    def __init__(self) -> None:
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(settings.reranker_model)

    def rerank(
        self, query: str, docs: List[str], top_k: int = 5
    ) -> List[Tuple[str, float]]:
        scores = self._model.predict([(query, d) for d in docs])
        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]
