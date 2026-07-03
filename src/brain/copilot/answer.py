"""Turn retrieved evidence into a trustworthy answer.

The answer is built, not guessed:
  - context is assembled from graph facts + matched passages, each numbered so
    the model can cite it as [n];
  - confidence is *computed* from how sure extraction was, how well-linked the
    facts are, how strongly passages matched, and whether sources agree — a weak
    answer says it is weak instead of sounding falsely certain;
  - every answer carries clickable citations back to source documents;
  - framing is role-aware and personal data is redacted for roles not cleared.

The LLM is injected (any `.generate(prompt, system)`), so this is testable with a
stub and swaps providers for free. **It is also optional.** When no cloud/local
LLM is configured (or a call fails), the copilot falls back to a genuinely
readable **local extractive answer** — the same cited evidence, organised into a
role-aware brief by deterministic code, not a "sorry, no answer" message. This
means the product's core value (finding the right facts, connecting them across
departments, scoring confidence) never depends on an API being reachable; the
LLM only adds a polished narrative on top when it's available.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import List, Optional

from brain.copilot.roles import DEFAULT_ROLE, can_see_pii, framing
from brain.ingest.confidence import agreement_boost, answer_confidence, clamp, label
from brain.retrieval.knowledge import Evidence, KnowledgeBase, Retrieved
from brain.schema import SourceRef

_SYSTEM_RULES = (
    "Answer ONLY from the numbered context. Cite every claim with its source "
    "number like [1]. If the context does not contain the answer, say so plainly "
    "— do not invent tags, dates, or numbers."
)


@dataclass
class Citation:
    n: int
    kind: str
    doc_id: str
    doc_type: str
    path: str
    page: Optional[int]
    snippet: str


@dataclass
class Answer:
    question: str
    role: str
    text: str
    confidence: float
    confidence_label: str
    citations: List[Citation] = field(default_factory=list)
    assets: List[str] = field(default_factory=list)
    signals: dict = field(default_factory=dict)
    source_doc_types: List[str] = field(default_factory=list)
    mode: str = "generative"          # "generative" (LLM) | "extractive" (local, no LLM)
    retrieval_method: str = "keyword"


_ROLE_OPENERS = {
    "technician": "Here's what the records show, in short:",
    "engineer": "Based on the linked records and evidence:",
    "safety_officer": "From a safety and compliance standpoint, the records show:",
    "auditor": "The following evidence directly supports this:",
    "operator": "Current status per the records:",
}


def _redact(text: str, names: List[str]) -> str:
    for nm in names:
        if nm:
            text = re.sub(re.escape(nm), "[name withheld]", text)
    return text


def _linkage_score(n_graph_facts: int) -> float:
    # Saturating: more connected facts -> better linked, diminishing returns.
    return clamp(1.0 - math.exp(-n_graph_facts / 5.0))


class Copilot:
    def __init__(self, kb: KnowledgeBase, llm, max_graph: int = 12, max_passages: int = 5):
        self.kb = kb
        self.llm = llm
        self.max_graph = max_graph
        self.max_passages = max_passages
        self._person_names = [
            (n.properties.get("name") or n.value)
            for n in kb.g.nodes_by_label("Person")
        ]

    def _select(self, r: Retrieved):
        graph = r.graph_evidence[: self.max_graph]
        passages = sorted(r.passage_evidence, key=lambda e: e.score, reverse=True)[: self.max_passages]
        return graph + passages

    def _context_block(self, items: List[Evidence], role: str):
        citations: List[Citation] = []
        lines: List[str] = []
        redact = not can_see_pii(role)
        for i, ev in enumerate(items, start=1):
            stmt = _redact(ev.statement, self._person_names) if redact else ev.statement
            snippet = (ev.source.evidence or ev.statement)[:200]
            if redact:                       # never leak PII through the raw snippet
                snippet = _redact(snippet, self._person_names)
            tag = f"{ev.kind}/{ev.doc_type}" if ev.doc_type else ev.kind
            lines.append(f"[{i}] ({tag}) {stmt}")
            citations.append(Citation(
                n=i, kind=ev.kind, doc_id=ev.source.doc_id, doc_type=ev.doc_type,
                path=ev.source.path, page=ev.source.page, snippet=snippet,
            ))
        return "\n".join(lines), citations

    def _confidence(self, r: Retrieved, items: List[Evidence]) -> dict:
        confs = [e.confidence for e in items] or [0.0]
        extraction = sum(confs) / len(confs)
        linkage = _linkage_score(len(r.graph_evidence))
        passages = [e for e in items if e.kind == "passage"]
        retrieval = max((e.confidence for e in passages), default=0.0)
        agreement = agreement_boost(confs)
        score = answer_confidence(extraction, linkage, retrieval, agreement)
        return {"extraction": round(extraction, 3), "linkage": round(linkage, 3),
                "retrieval": round(retrieval, 3), "agreement": round(agreement, 3),
                "overall": round(score, 3)}

    def _extractive_answer(self, items: List[Evidence], role: str, redact: bool) -> str:
        """Compose a readable, role-framed answer directly from the evidence —
        no LLM involved. The strongest facts lead, but citation numbers match
        the numbering the citation panel already shows."""
        opener = _ROLE_OPENERS.get(role, "Based on the available records:")
        ranked = sorted(enumerate(items, start=1), key=lambda t: t[1].confidence, reverse=True)
        lines = []
        for i, ev in ranked[:6]:
            stmt = _redact(ev.statement, self._person_names) if redact else ev.statement
            lines.append(f"{i}. {stmt} [{i}]")
        return opener + "\n\n" + "\n".join(lines)

    def answer(self, question: str, role: str = DEFAULT_ROLE) -> Answer:
        r = self.kb.retrieve(question, top_k=self.max_passages)
        items = self._select(r)
        context, citations = self._context_block(items, role)
        signals = self._confidence(r, items)
        redact = not can_see_pii(role)

        if not items:
            return Answer(question=question, role=role,
                          text="I don't have any information on that in the "
                               "current document set.",
                          confidence=0.0, confidence_label="Low",
                          assets=r.assets, signals=signals, mode="extractive",
                          retrieval_method=r.retrieval_method)

        mode = "generative"
        if self.llm is not None:
            system = f"{framing(role)}\n\n{_SYSTEM_RULES}"
            prompt = (f"Question: {question}\n\nContext:\n{context}\n\n"
                      "Answer the question using the context above, citing sources as [n].")
            try:
                text = self.llm.generate(prompt, system=system).strip()
                if not text:
                    raise ValueError("empty response")
            except Exception:
                text = self._extractive_answer(items, role, redact)
                mode = "extractive"
        else:
            text = self._extractive_answer(items, role, redact)
            mode = "extractive"

        if redact:
            text = _redact(text, self._person_names)

        return Answer(
            question=question, role=role, text=text,
            confidence=signals["overall"], confidence_label=label(signals["overall"]),
            citations=citations, assets=r.assets, signals=signals,
            source_doc_types=sorted({e.doc_type for e in items if e.doc_type}),
            mode=mode, retrieval_method=r.retrieval_method,
        )
