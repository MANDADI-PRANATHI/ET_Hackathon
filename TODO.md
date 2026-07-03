# TODO / Task Tracker — Unified Asset & Operations Brain

Living task tracker for session handoff. Update on every meaningful change.
Plan of record: [PLAN.md](PLAN.md). Engineering guide: [CLAUDE.md](CLAUDE.md).

Legend: ✅ done · 🔄 in progress · ⏳ pending · 📝 decision · ⚠️ limitation

---

## Level status
- ✅ **Level 0 — Foundation** (infra, ontology, provider switch, schema, synth data, health-check)
- ✅ **Level 1 — Read & extract** (router, readers, deterministic + AI extraction, chunking, embeddings hook, benchmark, keyword baseline)
- 🔄 **Level 2 — Knowledge graph build** (merge staged facts into Neo4j, entity resolution, live re-ingest)
- ⏳ **Level 3 — GraphRAG copilot** (retrieval, confidence, citations, role-aware, API + mobile UI + voice)
- ⏳ **Level 4a — Compliance & QMS agent** (rule engine, evidence packages, CAPA)
- ⏳ **Level 4b — Maintenance & RCA agent** (readings adapter, time-series, predictive)
- ⏳ **Level 4c — Lessons-learned & proactive warnings**
- ⏳ **Level 5 — Live scorecard, ontology-swap demo, RBAC, arch diagram, deck, video**

---

## Level 1 — DONE (detail)
- ✅ Staging data model `brain/schema.py` (NodeFact/EdgeFact/Chunk/StagedDoc, source+confidence+extractor).
- ✅ Deterministic extraction `ingest/patterns.py`: tag/reg/date regex, normalisation, priority-resolved non-overlapping matches, document-reference false-positive rejection.
- ✅ Chunking `ingest/chunk.py` (paragraph-aware, overlap, char spans).
- ✅ Confidence `ingest/confidence.py` (base per extractor, agreement boost, answer blend + labels).
- ✅ Readers: `structured` (CSV→facts, no AI), `text` (.txt/.eml), `document` (Docling, lazy), `drawing` (vision, injectable).
- ✅ Router `ingest/router.py` (folder→doc_type, ext→reader, stable ids).
- ✅ AI prose extraction `ingest/extract.py` (schema-fenced, evidence-quoted, confidence-capped, LLM injected).
- ✅ Pipeline `ingest/pipeline.py` + `scripts/ingest.py` (`--structured-only`, `--path`, `--ai`, `--embeddings`).
- ✅ Keyword baseline `search/keyword.py` (BM25, stdlib) for time-to-answer metric.
- ✅ Extraction benchmark `eval/` (fixtures + labels + scorer) — currently **P/R/F1 = 1.0** on all types.
- ✅ Narrative docs added to `generate_synthetic.py` (incident/email/SOP) → cross-functional links (PSV-110B touched by 7 doc types).
- ✅ Tests `tests/test_level1.py` — 15 passing on L0 deps.
- ✅ `requirements-l1.txt`.

## 🔄 Level 2 — NEXT (immediate actions)
1. `brain/stores/graph_writer.py` — load `data/staging/*.json` into Neo4j: MERGE nodes by (label, key→value), merge properties (non-null wins), create edges; carry source/confidence/extractor onto elements.
2. Entity resolution `brain/graph/resolve.py` — normalise tags, alias lists, similarity for unclear cases, **do not over-merge** P-101A vs P-101B; multi-source confidence via `agreement_boost`.
3. `scripts/build_graph.py` (Makefile `build-graph` already points here).
4. Live re-ingest: extract→compare→merge→update→refresh embeddings→invalidate cache; demo by dropping a new file.
5. Linkage-completeness + merge-accuracy metrics → `eval/`.
6. Graph visualisation export (for the demo) — e.g. a Cypher/JSON dump the UI can render.
7. Tests: resolution logic on L0 deps (pure functions); graph writer behind a driver stub or sk-if-no-neo4j.

---

## 📝 Key decisions
- Per-document staging; cross-document asset merge happens at Level 2 (keeps Level 1 stateless & parallelisable).
- Structured facts = confidence 1.0; regex = 0.9; AI ≤ 0.85; vision = 0.5 + needs_review. AI never outranks a table.
- Equipment-tag regex rejects hyphen-embedded refs and non-asset prefixes (WO/NCR/INC/SOP/…) to avoid bogus assets.
- Committed benchmark fixtures in `eval/fixtures` (stable, always runnable) — independent of the gitignored corpus.
- Real git commits per level (repo convention `feat(lN): …`) so sessions resume cleanly.

## ⚠️ Known limitations
- Docling page-level char mapping not wired → PDF citations resolve to document, not page.
- AI + vision paths verified via stubs only (no live model key in this environment).
- Neo4j/docling/genai not installed in the current dev env; those paths are import-safe and will run once deps + services are up.
