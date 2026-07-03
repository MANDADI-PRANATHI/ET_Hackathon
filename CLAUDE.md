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
6. **Local models first, cloud LLM last.** Retrieval quality (finding and
   ranking evidence), every agent verdict, and confidence scoring must never
   *require* a cloud API call — they run on local embeddings/reranker and plain
   code. The cloud/local LLM is an optional narrative layer on top, never the
   thing that makes an answer correct. See "Offline-first architecture" below.

## Offline-first architecture — why, and what it means for new code
Real deployment target: plants that legally cannot send drawings or incident
data to a foreign cloud (a genuine constraint for regulated Indian sites, not
a hypothetical). So the design keeps the LLM's blast radius small on purpose:

- **Retrieval is local hybrid search**, not a vector-DB-plus-API pattern:
  BM25 keyword + on-device embeddings (`providers/embeddings.LocalEmbedder`)
  fused by Reciprocal Rank Fusion, then reranked by a local cross-encoder
  (`LocalReranker`). See `retrieval/knowledge.py::search_passages`. All three
  stages are free, on-device, and the sole source of "which evidence is
  correct" — the LLM never decides that.
- **The copilot works with `llm=None`.** `copilot/answer.py::Copilot.answer`
  falls back to `_extractive_answer` — a deterministic, role-framed composition
  of the same cited evidence — whenever no LLM is configured *or* a call
  fails. This is not a degraded "sorry" path; it's a first-class mode
  (`Answer.mode == "extractive"`), and the UI treats it as such (⚡ badge, not
  an error state).
- **Answer faithfulness is measured locally too.** `copilot/faithfulness.py`
  scores whether an answer's claims are grounded in the cited evidence using
  embedding cosine similarity — no LLM-as-judge, no network call. It's an
  honest, narrower proxy (catches off-topic/hallucinated-topic answers; too
  coarse for fine-grained numeric fact-checking — that's what the
  deterministic agents are for) and the module docstring says so explicitly.
- **Embeddings are cached, not recomputed.** `scripts/embed.py` embeds every
  passage once and writes the vectors back into `data/staging/*.json`.
  `KnowledgeBase.ensure_embeddings()` only backfills what's missing. The API
  (`api/app.py::_load`) caps how much it will auto-embed at startup
  (`_MAX_STARTUP_EMBED`) so launch never silently takes minutes — beyond that
  threshold it starts on keyword search alone and tells you to run
  `make embed`. **Ingestion must preserve this cache**: `ingest_corpus` and the
  `--path` single-file mode both call `_carry_forward_embeddings()` before
  writing a re-ingested `StagedDoc`, matching cached vectors by
  `(chunk id, exact text)` so re-running `make ingest` after adding new
  documents never wipes out embeddings already paid for. If you touch the
  ingestion write path, keep this call in place — its regression test
  (`tests/test_embed_cache.py`) exists because this exact bug shipped once.
- **The remaining cloud-shaped surface is narrow and swappable**: prose fact
  extraction (`ingest/extract.py`), drawing/P&ID reading
  (`ingest/readers/drawing.py`), and the final answer's prose
  (`copilot/answer.py`). All three already work with `LLM_PROVIDER=ollama` +
  a local model (e.g. `qwen2.5:7b`, vision `qwen2.5vl:7b`) with **no code
  change** — the provider switch (`providers/llm.py::get_llm`) is the whole
  point. Prefer strengthening the local/Ollama path over adding
  Gemini-specific logic.

## Architecture (data flow)
```
corpus files ──▶ ingest (Level 1) ──▶ data/staging/*.json ──▶ build-graph (Level 2) ──▶ Neo4j
                    router                StagedDoc              GraphModel (merge+resolve)  graph + vector index
                    readers               (nodes/edges/chunks,    metrics + viz export (JSON)       │
                    patterns (regex)       embeddings cached)                                       ▼
                    extract (AI, optional)                                  copilot (Level 3) · agents (Level 4)
                    chunk / embed (embed.py)                                scorecard (Level 5)

Level 2 note: the merge/resolution logic lives in a storage-free `GraphModel`
(pure, testable); the Neo4j writer just persists it. `build_graph.py` always
produces the model, metrics, and viz export, and writes to Neo4j when reachable.

Level 3 note: retrieval is LOCAL hybrid search (BM25 + embeddings, RRF-fused,
cross-encoder reranked) — no API call. The LLM (cloud or local via Ollama) only
writes the final prose; without one, a deterministic extractive answer is
composed from the same cited evidence instead.
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
| `ingest/pipeline.py` | Orchestrates route→read→extract→chunk→embed→stage. `_carry_forward_embeddings` protects the embed cache across re-ingestion (see offline-first section above). |
| `search/keyword.py` | BM25 baseline ("traditional search") for the time-to-answer metric. |
| `graph/model.py` | In-memory merged graph: MERGE by (label, canonical value), property precedence by extractor tier, confidence via agreement, provenance. Storage-free & testable. |
| `graph/resolve.py` | Entity resolution: canonicalisation, `same_asset`, `base_tag`, `propose_merges` (no over-merge of A/B backups). |
| `graph/metrics.py` | Linkage completeness (asset coverage), orphans, needs-review counts. |
| `graph/export.py` | Clean asset-centric JSON for the demo graph visualisation. |
| `stores/graph_writer.py` | Persist the merged graph into Neo4j (lazy, provenance onto elements). |
| `retrieval/knowledge.py` | GraphRAG KnowledgeBase: spot assets (tag/name/class), graph-neighbourhood evidence, **local hybrid passage search** (BM25 + dense, RRF-fused, cross-encoder reranked — `search_passages`), combined retrieve. `ensure_embeddings()` backfills missing vectors in memory. Runs on the in-memory graph — no DB needed. |
| `copilot/answer.py` | Cited, confidence-scored, role-aware answers; LLM injected and **optional** — falls back to a deterministic `_extractive_answer` from the same evidence when no LLM is configured or a call fails (`Answer.mode`). |
| `copilot/faithfulness.py` | Local, embedding-based answer-faithfulness scorer — no LLM judge, no API call. Scoped honestly: catches off-topic hallucination, not fine-grained numeric errors. |
| `copilot/roles.py` | Role framing + PII gating (redacts Person for non-cleared roles). |
| `api/app.py` | FastAPI: /ask, /graph, /roles, /health, /compliance, /rca, /warnings, /scorecard, /assets, /ui. Loads local embedder+reranker eagerly (best-effort) and the cloud/local LLM best-effort at startup; `SUTRADHAR_SKIP_LOCAL_MODELS=1` skips real model loads (used by tests). |
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
python run.py                                 # one command: setup + launch (see README)
make up && make init && make synth            # infra + schema + synthetic corpus (Level 0)
make ingest-structured                        # Level 1 without AI/embeddings (L0 deps only)
make ingest                                    # Level 1 full (needs L1 deps + LLM configured)
make embed                                     # cache passage embeddings once (local, no API)
python eval/extraction_eval.py                 # entity-extraction accuracy benchmark
python -m pytest tests/ -q                     # regression tests (L0 deps only)
```

## Testing
- `tests/` runs on Level 0 deps — no Neo4j/LLM/docling/**real transformer
  models** needed. Uses stubbed LLMs, stubbed embedders/rerankers, and tmp
  files. Keep it that way so tests stay fast and always runnable.
- Service/LLM-dependent code is exercised via injection (pass a stub) rather than
  by mocking network calls. `tests/test_offline.py` shows the pattern for local
  models: `StubEmbedder`/`StubReranker` with hand-picked vectors, not a real
  `sentence-transformers` load.
- `tests/test_api.py` sets `SUTRADHAR_SKIP_LOCAL_MODELS=1` before importing the
  app so `TestClient` doesn't eagerly load real embedding/reranker models (this
  regressed the suite from <1s to 100s+ once — keep the env var set in any new
  API test fixture). One exception is deliberate: the `/scorecard` route always
  computes the real, embedding-backed faithfulness metric, so that one test is
  allowed to be slower — it's validating the real number, not the wiring.
- If you add a benchmark/eval script that needs a real local model
  (`LocalEmbedder`/`LocalReranker`), wire its regression-suite counterpart in
  `tests/test_levelN.py` via `monkeypatch.setattr` on the eval module's
  function (see `test_level5.py::test_scorecard_has_all_metrics...`), not by
  calling the real model in the fast suite.
- `tests/test_embed_cache.py` pins a real regression: re-ingesting the corpus
  must never discard cached embeddings for unchanged chunks. Don't remove the
  `_carry_forward_embeddings()` call in `ingest/pipeline.py` without keeping
  this test green.

## Known limitations / future work
- Docling per-page char mapping is not yet wired, so PDF citations resolve to the
  document, not the exact page. Refinement noted in `readers/document.py`.
- AI prose extraction is validated with stubs; live-model accuracy needs a run
  once an API key / Ollama is available. It is capped below structured confidence
  by design.
- Vision drawing reader is injectable and import-safe but unverified against a
  real P&ID (needs a vision model). Day-1 de-risk spike in PLAN.md §10.
- The local faithfulness scorer (`copilot/faithfulness.py`) is a topical-grounding
  proxy, not a fine-grained fact-checker — documented explicitly in its module
  docstring so it isn't oversold. It reliably catches an answer about the wrong
  topic/asset; it will not catch a right-topic answer with one wrong number.
- Embedding 6k+ passages on CPU takes ~2–3 minutes the *first* time
  (`make embed`); this is a one-time, fully local cost (cached to
  `data/staging/*.json` afterwards), not a per-request one. Startup
  auto-embeds only up to `_MAX_STARTUP_EMBED` (500) missing chunks to keep
  `python run.py` / `make api` launches fast.
