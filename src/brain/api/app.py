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
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from brain.copilot.answer import Copilot
from brain.copilot.roles import DEFAULT_ROLE, ROLE_FRAMING
from brain.graph.export import asset_list, asset_subgraph, graph_json
from brain.ontology import load_ontology
from brain.retrieval.knowledge import KnowledgeBase

STAGING = Path(os.environ.get("STAGING_DIR", "data/staging"))
_MAX_STARTUP_EMBED = 500   # embed on the fly up to this many missing vectors


class AskRequest(BaseModel):
    question: str
    role: str = DEFAULT_ROLE


class _State:
    kb: KnowledgeBase | None = None
    copilot: Copilot | None = None
    llm_ready: bool = False
    semantic_ready: bool = False
    rerank_ready: bool = False


state = _State()


def _load() -> None:
    """Build the knowledge base and wire in every model — local ones eagerly
    (they're free and make retrieval itself work without any API call), the
    cloud LLM only best-effort (it's optional narrative polish on top)."""
    onto = load_ontology()

    # Tests set this to skip loading real transformer models (keeps the suite
    # on Level 0 deps and fast — see tests/test_api.py).
    skip_local = os.environ.get("SUTRADHAR_SKIP_LOCAL_MODELS") == "1"

    embedder = None
    if not skip_local:
        try:
            from brain.providers.embeddings import LocalEmbedder
            embedder = LocalEmbedder()
            state.semantic_ready = True
        except Exception:  # noqa: BLE001 - falls back to keyword search, still works
            state.semantic_ready = False

    reranker = None
    if not skip_local:
        try:
            from brain.providers.embeddings import LocalReranker
            reranker = LocalReranker()
            state.rerank_ready = True
        except Exception:  # noqa: BLE001 - falls back to un-reranked hybrid order
            state.rerank_ready = False

    state.kb = KnowledgeBase.load(STAGING, onto)   # embeddings wired in below
    if embedder is not None:
        missing = sum(1 for c in state.kb.chunks if not c.embedding)
        if 0 < missing <= _MAX_STARTUP_EMBED:
            state.kb.ensure_embeddings(embedder)
        elif missing > _MAX_STARTUP_EMBED:
            # Embedding thousands of passages live would make every launch slow.
            # Keep boot fast; keyword search still covers 100% of passages, and
            # `make embed` caches vectors to data/staging/*.json permanently.
            print(f"[note] {missing} passages have no cached embedding — skipping "
                 f"at startup to keep launch fast (keyword search still covers "
                 f"them). Run `make embed` once to cache semantic vectors for "
                 f"instant startup from then on.")

    llm = None
    try:
        from brain.providers.llm import get_llm
        llm = get_llm()
        state.llm_ready = True
    except Exception:  # noqa: BLE001 - copilot still works without a writer LLM
        state.llm_ready = False
    state.copilot = Copilot(state.kb, llm, embedder=embedder, reranker=reranker)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _load()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Sutradhar — Asset & Operations Brain", version="0.5",
                  lifespan=_lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "assets": len(state.kb.g.nodes_by_label("Asset")) if state.kb else 0,
            "chunks": len(state.kb.chunks) if state.kb else 0,
            "llm_ready": state.llm_ready,
            "semantic_ready": state.semantic_ready,
            "rerank_ready": state.rerank_ready,
            # The system is fully functional offline: local hybrid retrieval +
            # extractive answers need no API call. The cloud LLM only adds a
            # polished narrative on top when it's reachable.
            "offline_capable": True,
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
            "mode": answer.mode,
            "retrieval_method": answer.retrieval_method,
        }

    @app.get("/assets")
    def assets() -> dict:
        return asset_list(state.kb.g)

    @app.get("/graph")
    def graph(asset: str = "", include_chunks: bool = False, limit: int = 28) -> dict:
        # Per-asset neighbourhood (scales to a huge graph); full graph only when
        # no asset is given (used by tests / small datasets).
        if asset:
            return asset_subgraph(state.kb.g, asset, limit=limit)
        return graph_json(state.kb.g, include_chunks=include_chunks)

    @app.get("/scorecard")
    def scorecard() -> dict:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "eval"))
        from scorecard import build_scorecard
        return build_scorecard()

    @app.get("/rca/{asset}")
    def rca(asset: str) -> dict:
        import os as _os
        from brain.agents.rca import investigate
        from brain.stores.readings import FileReadingsSource
        readings = FileReadingsSource(_os.environ.get("READINGS_FILE",
                                                       "data/readings/readings.csv"))
        report = investigate(state.kb.g, asset, readings=readings, llm=state.copilot.llm)
        return {
            "asset": report.asset, "assessed_on": report.assessed_on,
            "narrative": report.narrative,
            "findings": [{"cause": f.cause, "kind": f.kind,
                          "confidence": f.confidence, "rationale": f.rationale}
                         for f in report.findings],
            "trends": [vars(t) for t in report.trends],
            "recommendations": [vars(r) for r in report.recommendations],
            "schedule": report.schedule,
            "report_markdown": report.to_markdown(),
        }

    @app.get("/warnings")
    def warnings() -> dict:
        import os as _os
        from brain.agents.lessons import generate_warnings
        from brain.stores.readings import FileReadingsSource
        readings = FileReadingsSource(_os.environ.get("READINGS_FILE",
                                                       "data/readings/readings.csv"))
        report = generate_warnings(state.kb.g, readings=readings)
        return {
            "generated_on": report.generated_on,
            "warnings": [{"asset": w.asset, "severity": w.severity,
                          "message": w.message, "basis": w.basis} for w in report.warnings],
            "patterns": [{"kind": p.kind, "key": p.key, "count": p.count,
                          "assets": sorted(set(p.assets))} for p in report.patterns],
            "report_markdown": report.to_markdown(),
        }

    @app.get("/compliance")
    def compliance() -> dict:
        from brain.agents.compliance import run_compliance
        report = run_compliance(state.kb.g)
        return {
            "assessed_on": report.assessed_on,
            "summary": report.summary,
            "results": [
                {"asset": r.asset, "code": r.code, "requirement": r.requirement_id,
                 "status": r.status, "detail": r.detail,
                 "evidence": (r.evidence.path if r.evidence else None)}
                for r in report.results
            ],
            "evidence_package_markdown": report.to_markdown(),
            "drafts": report.drafts(),
        }

    # Serve the single-file UI (if present) at /ui.
    web_dir = Path(__file__).resolve().parents[3] / "web"
    if web_dir.exists():
        from fastapi.staticfiles import StaticFiles
        app.mount("/ui", StaticFiles(directory=str(web_dir), html=True), name="ui")

    return app


app = create_app()
