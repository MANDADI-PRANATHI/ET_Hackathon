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
6. **Plain code before a model call, every time.** Retrieval, every agent
   verdict, and confidence scoring run on plain code — they never *require* a
   cloud API. The cloud/local LLM is an optional narrative layer on top, never
   the thing that makes an answer correct.
7. **Justify every dependency against a measured need, not a hypothetical one.**
   A hybrid embeddings+reranker retrieval stack was built, benchmarked against
   plain keyword search, found to score identically on this system's own eval,
   and was removed — see "Why keyword search, not embeddings?" below. Don't
   re-add ML-model complexity to retrieval without first showing a real
   benchmark where it changes the answer.

## Why keyword search, not embeddings? (a decision, not an oversight)
Retrieval used to be a hybrid pipeline: BM25 + on-device embeddings, fused with
Reciprocal Rank Fusion, then reranked by a local cross-encoder. It was measured
against plain keyword search on this project's own benchmark
(`eval/copilot_bench.py`, 8 questions) and **scored identically — 1.0
groundedness, 1.0 cross-functional discovery, 1.0 asset-spotting, both ways.**

The reason it made no difference: most of an answer's correctness comes from
graph traversal (`KnowledgeBase.spot_assets` + `asset_facts`), not passage
ranking — the system finds the asset tag in the question and pulls *every*
connected fact from the graph, which is an exact lookup, not a search problem.
Passage retrieval is a secondary layer on top, and on this corpus keyword
search was good enough for it.

Given no measured quality gain, the hybrid stack was stripped back because it
cost real things: ~4 GB of downloaded models (torch, transformers, two
HuggingFace model checkpoints), 20-30s of model-loading at every startup, a
whole embedding-cache subsystem (`scripts/embed.py`, backfill logic, a
carry-forward-on-reingest fix for a bug that subsystem itself introduced), and
a local "faithfulness" scorer that duplicated ground already covered by the
deterministic agents. None of that complexity was earning its keep. **If you
're tempted to re-add embeddings/reranking to retrieval, run
`eval/copilot_bench.py` before and after — only keep it if the numbers actually
move.** (`git log` has the removed implementation if it's ever needed as a
reference: see the commit that reintroduces plain keyword search.)

## Architecture (data flow)
```
corpus files ──▶ ingest (Level 1) ──▶ data/staging/*.json ──▶ build-graph (Level 2) ──▶ Neo4j
                    router                StagedDoc                GraphModel (merge+resolve)  graph + vector index
                    readers               (nodes/edges/chunks)     metrics + viz export (JSON)       │
                    patterns (regex)                                                                ▼
                    extract (AI, optional)                                    copilot (Level 3) · agents (Level 4)
                    chunk                                                     scorecard (Level 5)

Level 2 note: the merge/resolution logic lives in a storage-free `GraphModel`
(pure, testable); the Neo4j writer just persists it. `build_graph.py` always
produces the model, metrics, and viz export, and writes to Neo4j when reachable.

Level 3 note: retrieval is graph traversal + plain keyword search (BM25) — no
API call, no ML model to load. The LLM (cloud or local via Ollama) only writes
the final prose; without one, a deterministic extractive answer is composed
from the same cited evidence instead.
```

### The staging contract (`brain/schema.py`) — the spine of the system
Level 1 turns every document into a `StagedDoc` with three lists:
- **`NodeFact`** — a graph node, keyed by `(label, key -> value)`, with `properties`.
- **`EdgeFact`** — a link between two nodes by their `(label, value)`.
- **`Chunk`** — a searchable passage.

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
| `stores/neo4j_init.py` | Create constraints + a vector-index schema stub from the ontology (unused by the current retrieval path — a future Neo4j-backed semantic search hook, not required for anything today). |
| `ingest/patterns.py` | Deterministic regex extraction + tag/reg normalisation. Priority-resolved, non-overlapping; rejects document-reference false positives. |
| `ingest/chunk.py` | Paragraph-aware passage windowing with overlap. |
| `ingest/confidence.py` | Base confidences per extractor; agreement boost; final answer-confidence blend. |
| `ingest/readers/` | `structured` (CSV→facts, no AI), `text` (.txt/.eml, stdlib), `document` (Docling PDFs, lazy), `drawing` (vision P&ID, lazy/injectable). |
| `ingest/router.py` | Folder→doc_type, extension→reader, stable doc ids. |
| `ingest/extract.py` | AI prose extraction — schema-fenced, evidence-quoted, confidence-capped, LLM injected. |
| `ingest/pipeline.py` | Orchestrates route→read→extract→chunk→stage. |
| `search/keyword.py` | BM25 keyword search — the passage-retrieval engine (not just a "traditional search" baseline). |
| `graph/model.py` | In-memory merged graph: MERGE by (label, canonical value), property precedence by extractor tier, confidence via agreement, provenance. Storage-free & testable. |
| `graph/resolve.py` | Entity resolution: canonicalisation, `same_asset`, `base_tag`, `propose_merges` (no over-merge of A/B backups). |
| `graph/metrics.py` | Linkage completeness (asset coverage), orphans, needs-review counts. |
| `graph/export.py` | Clean asset-centric JSON for the demo graph visualisation. |
| `stores/graph_writer.py` | Persist the merged graph into Neo4j (lazy, provenance onto elements). |
| `retrieval/knowledge.py` | GraphRAG KnowledgeBase: spot assets (tag/name/class), graph-neighbourhood evidence, keyword passage search (`search_passages`), combined `retrieve`. Runs on the in-memory graph — no DB needed. |
| `copilot/answer.py` | Cited, confidence-scored, role-aware answers; LLM injected and **optional** — falls back to a deterministic `_extractive_answer` from the same evidence when no LLM is configured or a call fails (`Answer.mode`). |
| `copilot/roles.py` | Role framing + PII gating (redacts Person for non-cleared roles). |
| `api/app.py` | FastAPI: /ask, /graph, /roles, /health, /compliance, /rca, /warnings, /scorecard, /assets, /ui. Builds the knowledge base once at startup; the LLM is loaded best-effort. |
| `agents/compliance.py` | Hybrid compliance: LLM authors a checkable rule (`parse_clause`), plain code decides MET/GAP/UNKNOWN (`check_requirement`); evidence package + NCR/CAPA drafts. Curated RULESET ships with the profile. |
| `stores/readings.py` | Readings adapter (ReadingsSource protocol; FileReadingsSource replay) + deterministic trend `analyze`. OPC-UA/MQTT implement the same interface. |
| `agents/rca.py` | RCA agent: fuse graph history + readings → ranked cited findings, predictive recommendation, optimised schedule. Signals are code; narrative is optional LLM. |
| `agents/lessons.py` | Lessons-learned: `find_patterns` (recurring findings/failure modes/actions, family clusters) + `generate_warnings` (compliance gaps + trends + recurring findings → prioritised feed). |

## Conventions
- Every module starts with a plain-English docstring explaining *why*.
- `from __future__ import annotations` at the top; type-hint everything.
- Heavy/optional SDKs (neo4j, docling, google-genai, ollama) are **imported
  lazily inside functions**, so importing a module never forces a dependency
  the current path doesn't use.
- Comments explain intent for a non-expert reader, matching the existing style.
- Keep the tool stack small — a new dependency must earn its place, and prove
  it with a benchmark, not just a plausible-sounding argument (see "Why
  keyword search, not embeddings?" above for what happens when this rule is
  followed after the fact).

## How to run
```bash
python run.py                                 # one command: setup + launch (see README)
make up && make init && make synth            # infra + schema + synthetic corpus (Level 0)
make ingest-structured                        # Level 1 without AI (L0 deps only)
make ingest                                    # Level 1 full (needs L1 deps + LLM configured)
python eval/extraction_eval.py                 # entity-extraction accuracy benchmark
python -m pytest tests/ -q                     # regression tests (L0 deps only)
```

## Testing
- `tests/` runs on Level 0 deps — no Neo4j, no LLM, no docling, no ML model
  needed. Uses stubbed LLMs and tmp files. Keep it that way so tests stay fast
  and always runnable (the suite regressed to 100s+ once, when a local
  embedding model got loaded eagerly in a test fixture — see the "Why keyword
  search" note above for the fuller story of why that stack is gone now).
- Service/LLM-dependent code is exercised via injection (pass a stub) rather than
  by mocking network calls.

## Known limitations / future work
- Docling per-page char mapping is not yet wired, so PDF citations resolve to the
  document, not the exact page. Refinement noted in `readers/document.py`.
- AI prose extraction is validated with stubs; live-model accuracy needs a run
  once an API key / Ollama is available. It is capped below structured confidence
  by design.
- Vision drawing reader is injectable and import-safe. Validated once with a live
  model call against a generated synthetic P&ID (`eval/vision_probe.py`) — 7/7
  planted tags read correctly (equipment tags, an instrument tag, a line number).
  A real scanned drawing (noise, rotation, dense linework, symbol variety) remains
  untested; treat that as the open gap, not the reader itself.
- The Ollama path (`LLM_PROVIDER=ollama`) is code-complete but has never been
  run against a live Ollama server in development — treat it as untested, not
  as a demonstrated capability, until it's actually exercised.
- Benchmark scores in `eval/` are self-authored (the same person who built the
  system wrote the test questions) — treat "1.0" as "the pipeline works as
  designed," not as independent proof of generalization to unseen questions.
