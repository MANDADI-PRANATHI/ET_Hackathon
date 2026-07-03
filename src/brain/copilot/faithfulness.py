"""Answer faithfulness — measured locally, no LLM judge required.

RAGAS-style faithfulness normally asks a language model "is this claim
supported by the context?" for every sentence. That's expensive and, worse,
makes the *evaluation* of the product depend on the same kind of API call the
product itself tries not to depend on. Instead we measure semantic support
directly with the local embedding model: split the answer into sentences,
embed each one, and check its similarity against the cited evidence. This runs
anywhere the local embedder runs — fully offline, fully reproducible.

It's a proxy, not a substitute for an LLM judge, and we're explicit about its
scope: embedding similarity is a *topical-grounding* signal — it reliably
catches an answer that talks about the wrong asset or an unretrieved topic
(genuine hallucination), but it is too coarse to catch a subtly wrong number
or date attached to the *right* entity. That fine-grained correctness is what
the deterministic agents (compliance's exact date math, RCA's exact trend
numbers) are for — this metric's job is narrower and it does that job without
a single network call.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> List[str]:
    parts = [s.strip() for s in _SENTENCE_SPLIT.split(text or "") if s.strip()]
    # Drop numbered-bullet artefacts ("1.") and very short fragments — they're
    # not independent claims worth scoring.
    return [p for p in parts if len(p) > 8]


def _cosine(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))   # embeddings from LocalEmbedder are normalised


@dataclass
class FaithfulnessResult:
    score: float                      # 0..1, mean best-match support per sentence
    per_sentence: List[float]
    n_sentences: int


def score_faithfulness(answer_text: str, evidence_texts: List[str], embedder) -> FaithfulnessResult:
    """For each answer sentence, find its best-matching evidence statement and
    take that similarity as its support. The answer's score is the mean."""
    sentences = split_sentences(answer_text)
    if not sentences or not evidence_texts:
        return FaithfulnessResult(score=0.0, per_sentence=[], n_sentences=len(sentences))

    sent_vecs = embedder.embed(sentences)
    ev_vecs = embedder.embed(evidence_texts)

    per_sentence = []
    for sv in sent_vecs:
        best = max(_cosine(sv, ev) for ev in ev_vecs)
        per_sentence.append(round(max(0.0, min(1.0, best)), 3))

    return FaithfulnessResult(
        score=round(sum(per_sentence) / len(per_sentence), 3),
        per_sentence=per_sentence,
        n_sentences=len(sentences),
    )
