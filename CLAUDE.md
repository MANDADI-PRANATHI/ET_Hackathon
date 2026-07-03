# CLAUDE.md — engineering guide for the Unified Asset & Operations Brain

Project codename **Sutradhar**. Full product plan: [PLAN.md](PLAN.md). This file
is the working guide for anyone (human or agent) continuing development. Current
task state lives in [TODO.md](TODO.md).

---

## What this is
An AI platform that ingests heterogeneous industrial documents, builds an
**asset-centric knowledge graph**, and answers questions / runs agents over it
(compliance, RCA, lessons-learned). ET AI Hackathon 2026, Problem Statement #8.
Submission target: **22 July 2026**.

## Golden rules (do not violate)
1. **Asset is the hub.** Every fact links back to an equipment tag. Model new
   information as connections to an `Asset`, not as an island.
2. **Cheapest reliable extractor wins.** Structured data → read columns (no AI).
   Predictable identifiers → regex (no AI). Prose → LLM, fenced by a schema.
   Never use the LLM for something a few lines of deterministic code do reliably.
3. **Every fact carries `source` + `confidence` + `extractor`.** No orphan facts.
   This is what powers citations and the trust story. See `brain/schema.py`.
4. **Everything behind a switch.** LLM provider (`get_llm()`), industry vocabulary
   (the ontology YAML), storage — swap without touching call sites.
5. **Degrade gracefully.** A missing API key, DB, or optional dependency must
   never crash a path that doesn't need it. The structured-only path runs on
   Level 0 deps alone.

## Architecture (data flow)
```
corpus files ──▶ ingest (Level 1) ──▶ data/staging/*.json ──▶ build-graph (Level 2) ──▶ Neo4j
                    router                StagedDoc              GraphModel (merge+resolve)  graph + vector index
                    readers               (nodes/edges/chunks)   metrics + viz export (JSON)       │
                    patterns (regex)                                                              ▼
                    extract (AI)                                            copilot (Level 3) · agents (Level 4)
                    chunk / embed                                           scorecard (Level 5)

Level 2 note: the merge/resolution logic lives in a storage-free `GraphModel`
(pure, testable); the Neo4j writer just persists it. `build_graph.py` always
produces the model, metrics, and viz export, and writes to Neo4j when reachable.
```

### The staging contract (`brain/schema.py`) — the spine of the system
Level 1 turns every document into a `StagedDoc` with three lists:
- **`NodeFact`** — a graph node, keyed by `(label, key -> value)`, with `properties`.
- **`EdgeFact`** — a link between two nodes by their `(label, value)`.
- **`Chunk`** — a searchable passage (embedding attached when available).

Every `NodeFact`/`EdgeFact` has `source: SourceRef`, `confidence: float`, and
`extractor` ∈ {`structured`, `regex`, `ai`, `vision`}. Level 2 merges NodeFacts
across documents by `(label, value)`; it never needs to know how a fact was found.

## Module map (`src/brain/`)
| Module | Responsibility |
|---|---|
| `config.py` | All settings, from `.env` (pydantic-settings). |
| `ontology.py` | Load/validate the swappable ontology profile; expose labels, patterns, PII labels. |
| `schema.py` | The staging data model (NodeFact/EdgeFact/Chunk/StagedDoc). |
| `providers/llm.py` | Gemini/Ollama text brain behind `get_llm()`. |
| `providers/embeddings.py` | Local BGE embedder + reranker (lazy). |
| `stores/neo4j_init.py` | Create constraints + vector index from the ontology. |
| `ingest/patterns.py` | Deterministic regex extraction + tag/reg normalisation. Priority-resolved, non-overlapping; rejects document-reference false positives. |
| `ingest/chunk.py` | Paragraph-aware passage windowing with overlap. |
| `ingest/confidence.py` | Base confidences per extractor; agreement boost; final answer-confidence blend. |
| `ingest/readers/` | `structured` (CSV→facts, no AI), `text` (.txt/.eml, stdlib), `document` (Docling PDFs, lazy), `drawing` (vision P&ID, lazy/injectable). |
| `ingest/router.py` | Folder→doc_type, extension→reader, stable doc ids. |
| `ingest/extract.py` | AI prose extraction — schema-fenced, evidence-quoted, confidence-capped, LLM injected. |
| `ingest/pipeline.py` | Orchestrates route→read→extract→chunk→embed→stage. |
| `search/keyword.py` | BM25 baseline ("traditional search") for the time-to-answer metric. |
| `graph/model.py` | In-memory merged graph: MERGE by (label, canonical value), property precedence by extractor tier, confidence via agreement, provenance. Storage-free & testable. |
| `graph/resolve.py` | Entity resolution: canonicalisation, `same_asset`, `base_tag`, `propose_merges` (no over-merge of A/B backups). |
| `graph/metrics.py` | Linkage completeness (asset coverage), orphans, needs-review counts. |
| `graph/export.py` | Clean asset-centric JSON for the demo graph visualisation. |
| `stores/graph_writer.py` | Persist the merged graph into Neo4j (lazy, provenance onto elements). |
| `retrieval/knowledge.py` | GraphRAG KnowledgeBase: spot assets (tag/name/class), graph-neighbourhood evidence, meaning search (embeddings or keyword fallback), combined retrieve. Runs on the in-memory graph — no DB needed. |
| `copilot/answer.py` | Cited, confidence-scored answers; LLM injected; honest "don't know". |
| `copilot/roles.py` | Role framing + PII gating (redacts Person for non-cleared roles). |
| `api/app.py` | FastAPI: /ask, /graph, /roles, /health, /compliance. KB built once at startup from staging. |
| `agents/compliance.py` | Hybrid compliance: LLM authors a checkable rule (`parse_clause`), plain code decides MET/GAP/UNKNOWN (`check_requirement`); evidence package + NCR/CAPA drafts. Curated RULESET ships with the profile. |
| `stores/readings.py` | Readings adapter (ReadingsSource protocol; FileReadingsSource replay) + deterministic trend `analyze`. OPC-UA/MQTT implement the same interface. |
| `agents/rca.py` | RCA agent: fuse graph history + readings → ranked cited findings, predictive recommendation, optimised schedule. Signals are code; narrative is optional LLM. |
| `agents/lessons.py` | Lessons-learned: `find_patterns` (recurring findings/failure modes/actions, family clusters) + `generate_warnings` (compliance gaps + trends + recurring findings → prioritised feed). |

## Conventions
- Every module starts with a plain-English docstring explaining *why*.
- `from __future__ import annotations` at the top; type-hint everything.
- Heavy/optional SDKs (neo4j, docling, google-genai, ollama, sentence-transformers)
  are **imported lazily inside functions**, so importing a module never forces a
  dependency the current path doesn't use.
- Comments explain intent for a non-expert reader, matching the existing style.
- Keep the tool stack small — a new dependency must earn its place (demo risk).

## How to run
```bash
make up && make init && make synth          # infra + schema + synthetic corpus (Level 0)
make ingest-structured                       # Level 1 without AI/embeddings (L0 deps only)
make ingest                                   # Level 1 full (needs L1 deps + LLM configured)
python eval/extraction_eval.py                # entity-extraction accuracy benchmark
python -m pytest tests/ -q                    # regression tests (L0 deps only)
```

## Testing
- `tests/` runs on Level 0 deps — no Neo4j/LLM/docling needed. Uses stubbed LLMs
  and tmp files. Keep it that way so tests stay fast and always runnable.
- Service/LLM-dependent code is exercised via injection (pass a stub) rather than
  by mocking network calls.

## Known limitations / future work
- Docling per-page char mapping is not yet wired, so PDF citations resolve to the
  document, not the exact page. Refinement noted in `readers/document.py`.
- AI prose extraction is validated with stubs; live-model accuracy needs a run
  once an API key / Ollama is available. It is capped below structured confidence
  by design.
- Vision drawing reader is injectable and import-safe but unverified against a
  real P&ID (needs a vision model). Day-1 de-risk spike in PLAN.md §10.
