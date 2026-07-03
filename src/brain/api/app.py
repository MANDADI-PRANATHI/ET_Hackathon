"""HTTP API for the copilot and the knowledge graph.

Endpoints (consumed by the Next.js UI, but usable from curl for the demo):
  GET  /health          liveness + what's loaded
  GET  /roles           available roles for the copilot
  POST /ask             {question, role} -> cited, confidence-scored answer
  GET  /graph           the asset-centric graph, for the visualisation

The knowledge base is built once at startup from data/staging (no Neo4j needed).
The LLM is optional: if none is configured, /ask still returns the retrieved,
cited evidence with a computed confidence.

Run:  make api   (uvicorn brain.api.app:app --reload)
"""
from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from brain.copilot.answer import Copilot
from brain.copilot.roles import DEFAULT_ROLE, ROLE_FRAMING
from brain.graph.export import graph_json
from brain.ontology import load_ontology
from brain.retrieval.knowledge import KnowledgeBase

STAGING = Path(os.environ.get("STAGING_DIR", "data/staging"))


class AskRequest(BaseModel):
    question: str
    role: str = DEFAULT_ROLE


class _State:
    kb: KnowledgeBase | None = None
    copilot: Copilot | None = None
    llm_ready: bool = False


state = _State()


def _load() -> None:
    onto = load_ontology()
    state.kb = KnowledgeBase.load(STAGING, onto)
    llm = None
    try:
        from brain.providers.llm import get_llm
        llm = get_llm()
        state.llm_ready = True
    except Exception:  # noqa: BLE001 - copilot still works without a writer LLM
        state.llm_ready = False
    state.copilot = Copilot(state.kb, llm)


def create_app() -> FastAPI:
    app = FastAPI(title="Sutradhar — Asset & Operations Brain", version="0.3")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        _load()

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "assets": len(state.kb.g.nodes_by_label("Asset")) if state.kb else 0,
            "chunks": len(state.kb.chunks) if state.kb else 0,
            "llm_ready": state.llm_ready,
        }

    @app.get("/roles")
    def roles() -> dict:
        return {"roles": sorted(ROLE_FRAMING), "default": DEFAULT_ROLE}

    @app.post("/ask")
    def ask(req: AskRequest) -> dict:
        answer = state.copilot.answer(req.question, role=req.role)
        return {
            "question": answer.question,
            "role": answer.role,
            "answer": answer.text,
            "confidence": answer.confidence,
            "confidence_label": answer.confidence_label,
            "signals": answer.signals,
            "assets": answer.assets,
            "cross_functional": len(answer.source_doc_types) > 1,
            "source_doc_types": answer.source_doc_types,
            "citations": [asdict(c) for c in answer.citations],
        }

    @app.get("/graph")
    def graph(include_chunks: bool = False) -> dict:
        return graph_json(state.kb.g, include_chunks=include_chunks)

    return app


app = create_app()
