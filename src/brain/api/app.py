"""HTTP API for the copilot and the knowledge graph.

Endpoints (consumed by the single-file UI at /ui, all usable from curl):
  GET  /health                    liveness + what's loaded
  GET  /roles                     available roles for the copilot
  POST /ask                       {question, role} -> cited, confidence-scored answer
  GET  /assets                    lightweight asset list
  GET  /assets/{tag}/timeline     one asset's dated history, chronological
  GET  /assets/{tag}/summary      asset dashboard header (status, risks, records)
  GET  /graph                     the asset-centric graph, for the visualisation
  GET  /scorecard                 live self-evaluation metrics
  GET  /rca/{asset}               root-cause investigation for one asset
  GET  /warnings                  proactive warnings + recurring patterns
  GET  /compliance                compliance report + evidence package + drafts
  POST /upload                    add one document -> ingest -> brain updates live
  POST /sync                      re-scan the corpus folder for new/changed files

The knowledge base is built once at startup from data/staging (no Neo4j needed)
and refreshed in place whenever /upload or /sync ingests something new. The LLM
is optional: if none is configured, /ask still returns the retrieved, cited
evidence with a computed confidence.

Run:  make api   (uvicorn brain.api.app:app --reload)
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from brain.copilot.answer import Copilot
from brain.copilot.roles import DEFAULT_ROLE, ROLE_FRAMING
from brain.graph.export import asset_list, asset_subgraph, asset_timeline, graph_json
from brain.ontology import load_ontology
from brain.retrieval.knowledge import KnowledgeBase

STAGING = Path(os.environ.get("STAGING_DIR", "data/staging"))
CORPUS = Path(os.environ.get("CORPUS_DIR", "data/corpus"))


class AskRequest(BaseModel):
    question: str
    role: str = DEFAULT_ROLE


class _State:
    kb: KnowledgeBase | None = None
    copilot: Copilot | None = None
    llm_ready: bool = False
    onto: dict | None = None


state = _State()


def _load() -> None:
    """Build the knowledge base (plain keyword search, no extra models to
    load) and wire in the LLM best-effort — it's optional narrative polish;
    /ask works without it via the copilot's extractive-answer fallback."""
    onto = load_ontology()
    state.onto = onto
    state.kb = KnowledgeBase.load(STAGING, onto)

    llm = None
    try:
        from brain.providers.llm import get_llm
        llm = get_llm()
        state.llm_ready = True
    except Exception:  # noqa: BLE001 - copilot still works without a writer LLM
        state.llm_ready = False
    state.copilot = Copilot(state.kb, llm)


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
            # Retrieval (keyword search + graph traversal) and every agent run
            # without an API call; the LLM only adds a polished narrative on
            # top when it's reachable — /ask still answers without one.
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

    @app.get("/assets/{asset}/timeline")
    def timeline(asset: str) -> dict:
        return asset_timeline(state.kb.g, asset)

    @app.get("/assets/{asset}/summary")
    def asset_summary(asset: str) -> dict:
        """The asset's dashboard header: status, last activity, linked records,
        open risks, related assets. Every number is computed from graph facts —
        'Needs attention' means an actual open gap or NCR, not a vibe."""
        from brain.agents.compliance import ruleset_from_ontology, run_compliance
        from brain.graph.resolve import base_tag
        g = state.kb.g
        node = g.nodes.get(("Asset", asset))
        if node is None:
            raise HTTPException(404, f"unknown asset: {asset}")

        counts: dict = {}
        docs = set()
        open_ncrs = []
        for e in g.neighbours("Asset", asset):
            other_label = e.from_label if e.from_label != "Asset" else e.to_label
            other_value = e.from_value if e.from_label != "Asset" else e.to_value
            if other_label == "Document":
                docs.add(other_value)
                continue
            if other_label in ("Chunk",):
                continue
            counts[other_label] = counts.get(other_label, 0) + 1
            if other_label == "NonConformance":
                ncr = g.nodes.get((other_label, other_value))
                if ncr and (ncr.properties.get("status") or "").lower() == "open":
                    open_ncrs.append(other_value)

        gaps = [r for r in run_compliance(
            g, ruleset=ruleset_from_ontology(state.onto)).gaps if r.asset == asset]
        events = asset_timeline(g, asset)["events"]

        base = base_tag(asset)
        related = sorted(a.value for a in g.nodes_by_label("Asset")
                         if a.value != asset and base_tag(a.value) == base)

        risks = ([f"Compliance gap: {r.detail}" for r in gaps]
                 + [f"Open non-conformance {n}" for n in open_ncrs])
        return {
            "asset": asset,
            "name": node.properties.get("name") or asset,
            "asset_class": node.properties.get("asset_class") or "",
            "criticality": node.properties.get("criticality") or "",
            "status": "Needs attention" if risks else "No open risks",
            "open_risks": risks,
            "last_activity": events[-1]["date"] if events else None,
            "documents": len(docs),
            "records": counts,
            "related_assets": related,
        }

    @app.post("/upload")
    async def upload(request: Request, filename: str,
                     folder: str = "project_files") -> dict:
        """Add one document to the brain, live: save into the corpus, ingest it
        (deterministic extractors — tables, tags, dates; no API call), and
        refresh the knowledge base so the very next /ask can use it."""
        from brain.ingest.router import FOLDER_DOCTYPE
        if folder not in FOLDER_DOCTYPE:
            raise HTTPException(400, f"unknown folder '{folder}' — "
                                     f"use one of {sorted(FOLDER_DOCTYPE)}")
        name = Path(filename).name
        if not name or name.startswith("."):
            raise HTTPException(400, "a plain filename is required")
        body = await request.body()
        if not body:
            raise HTTPException(400, "empty file")
        dest = CORPUS / folder / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)

        from brain.ingest.pipeline import ingest_file
        staged = ingest_file(dest, CORPUS, state.onto, enable_vision=False)
        if staged is None:
            dest.unlink()   # don't keep a file the pipeline can't read
            raise HTTPException(415, f"unsupported file type: {name}")
        staged.write(STAGING)
        _load()   # refresh the in-memory brain
        return {
            "doc_id": staged.document.id,
            "doc_type": staged.document.doc_type,
            "facts": len(staged.nodes) + len(staged.edges),
            "passages": len(staged.chunks),
            "assets_linked": sorted({n.value for n in staged.nodes
                                     if n.label == "Asset"}),
            "brain": {"assets": len(state.kb.g.nodes_by_label("Asset")),
                      "chunks": len(state.kb.chunks)},
        }

    @app.post("/sync")
    def sync() -> dict:
        """Incrementally re-scan the corpus folder: ingest files that are new or
        changed since they were last staged, leave the rest untouched. Point the
        corpus at a OneDrive/SharePoint/network-drive synced folder and this is
        the 'connect a folder, click Sync' onboarding path — no manual uploads."""
        from brain.ingest.pipeline import _iter_files, ingest_file
        from brain.ingest.router import DRAWING, route
        ingested, failed = [], []
        unchanged = 0
        for path in _iter_files(CORPUS):
            rt = route(path, CORPUS)
            if not rt.reader_kind or rt.reader_kind == DRAWING:
                continue   # unsupported here (drawings need the vision pass)
            staged_json = STAGING / f"{rt.doc_id}.json"
            if (staged_json.exists()
                    and staged_json.stat().st_mtime >= path.stat().st_mtime):
                unchanged += 1
                continue
            try:
                staged = ingest_file(path, CORPUS, state.onto, enable_vision=False)
            except Exception as e:  # noqa: BLE001 - one bad file must not stop the sync
                failed.append({"file": str(path), "error": f"{type(e).__name__}: {e}"})
                continue
            if staged is None:
                continue
            staged.write(STAGING)
            ingested.append(staged.document.id)
        if ingested:
            _load()   # refresh once, after the batch
        return {
            "ingested": ingested, "unchanged": unchanged, "failed": failed,
            "brain": {"assets": len(state.kb.g.nodes_by_label("Asset")),
                      "chunks": len(state.kb.chunks)},
        }

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
        from brain.agents.compliance import ruleset_from_ontology
        from brain.agents.rca import investigate
        from brain.stores.readings import FileReadingsSource
        readings = FileReadingsSource(_os.environ.get("READINGS_FILE",
                                                       "data/readings/readings.csv"))
        report = investigate(state.kb.g, asset, readings=readings, llm=state.copilot.llm,
                             ruleset=ruleset_from_ontology(state.onto))
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
        from brain.agents.compliance import ruleset_from_ontology
        from brain.agents.lessons import generate_warnings
        from brain.stores.readings import FileReadingsSource
        readings = FileReadingsSource(_os.environ.get("READINGS_FILE",
                                                       "data/readings/readings.csv"))
        report = generate_warnings(state.kb.g, readings=readings,
                                   ruleset=ruleset_from_ontology(state.onto))
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
        from brain.agents.compliance import ruleset_from_ontology, run_compliance
        report = run_compliance(state.kb.g, ruleset=ruleset_from_ontology(state.onto))
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
