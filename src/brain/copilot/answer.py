"""Fuse the retrieved passages + graph facts into a grounded answer with inline
citations. The model is told to answer ONLY from the context and to say so when
the context is insufficient (no hallucinating).
"""
from __future__ import annotations

from typing import Any, Dict, List

from brain.copilot.confidence import compute_confidence
from brain.providers.llm import get_llm

SYSTEM = (
    "You are an industrial knowledge assistant for plant staff. Answer ONLY from the "
    "provided context. Cite graph facts inline as [G1] and document passages as [S1] "
    "where you use them. If the context does not contain the answer, say you do not have "
    "enough information rather than guessing. Be concise, factual and practical."
)


def _sources(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for i, c in enumerate(chunks, start=1):
        out.append({
            "label": f"S{i}",
            "ref": c.get("doc") or c.get("path") or c.get("id"),
            "text": (c.get("text") or "").strip()[:300],
        })
    return out


def answer_question(retrieval: Dict[str, Any], llm=None, role=None) -> Dict[str, Any]:
    question, chunks, facts = retrieval["question"], retrieval["chunks"], retrieval["facts"]
    sources = _sources(chunks)
    labeled_facts = [
        {"label": f"G{i}", "text": f["text"], "confidence": f.get("confidence", 0.8)}
        for i, f in enumerate(facts, start=1)
    ]

    fact_block = "\n".join(f"[{g['label']}] {g['text']}" for g in labeled_facts) or "(none)"
    src_block = "\n".join(f"[{s['label']}] ({s['ref']}) {s['text']}" for s in sources) or "(none)"

    prompt = (
        f"QUESTION: {question}\n\n"
        f"GRAPH FACTS (from the plant knowledge graph):\n{fact_block}\n\n"
        f"DOCUMENT PASSAGES:\n{src_block}\n\n"
        "Write the answer now, citing graph facts as [G1] and passages as [S1] where used."
    )

    system = SYSTEM + (f" Tailor the wording and emphasis for a {role}." if role else "")
    text = (llm or get_llm()).generate(prompt, system=system)
    return {
        "question": question,
        "answer": text,
        "sources": sources,
        "facts": labeled_facts,
        "confidence": compute_confidence(chunks, facts),
    }
