# TODO / Task Tracker — Unified Asset & Operations Brain

Living task tracker for session handoff. Update on every meaningful change.
Plan of record: [PLAN.md](PLAN.md). Engineering guide: [CLAUDE.md](CLAUDE.md).

Legend: ✅ done · 🔄 in progress · ⏳ pending · 📝 decision · ⚠️ limitation

---

## Level status
- ✅ **Level 0 — Foundation** (infra, ontology, provider switch, schema, synth data, health-check)
- ✅ **Level 1 — Read & extract** (router, readers, deterministic + AI extraction, chunking, embeddings hook, benchmark, keyword baseline)
- ✅ **Level 2 — Knowledge graph build** (in-memory merge model, entity resolution, Neo4j writer, metrics, viz export, idempotent re-ingest)
- 🔄 **Level 3 — GraphRAG copilot** (retrieval, confidence, citations, role-aware, API + mobile UI + voice)
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

## Level 2 — DONE (detail)
- ✅ In-memory merge model `graph/model.py` — MERGE by (label, canonical value), property precedence by extractor tier (structured > regex/vision/ai), confidence via `agreement_boost`, provenance aggregation. Storage-free & fully testable.
- ✅ Entity resolution `graph/resolve.py` — canonicalisation (tags/regs/names), `same_asset`, `base_tag`, `propose_merges` (skips A/B backups → no over-merge), similarity.
- ✅ Neo4j writer `stores/graph_writer.py` — MERGE nodes/edges, provenance onto elements, lazy import, `--wipe`.
- ✅ Metrics `graph/metrics.py` — linkage completeness (asset coverage: documented/maintained/inspected), orphans, needs-review counts. Verified: score 0.958 on synthetic corpus.
- ✅ Viz export `graph/export.py` — clean asset-centric JSON (chunks hidden), hub flag.
- ✅ `scripts/build_graph.py` — merge + metrics + export always; Neo4j write degrades gracefully if unavailable. Idempotent re-run = the update path.
- ✅ Tests `tests/test_level2.py` — 10 passing (25 total).

## 🔄 Level 3 — NEXT (immediate actions)
1. `brain/retrieval/` — GraphRAG: entity-spot in question → graph hub + neighbours (Neo4j or in-memory model) + meaning-search over chunks (vector index; fall back to keyword when embeddings absent) → combine.
2. `brain/copilot/` — answer synthesis with citations (SourceRef → clickable), computed confidence (`answer_confidence` blend), role-aware framing, PII gating for Person.
3. Vector retrieval: Neo4j vector index query; graceful fallback to `search/keyword.py` + local embeddings cosine when Neo4j/embeddings unavailable.
4. `scripts/copilot.py` (CLI ask) + Makefile `copilot` target; FastAPI `api/` for the UI.
5. Expert-question benchmark `eval/` (answer quality + time-to-answer vs keyword baseline + cross-functional discovery rate).
6. Mobile-first Next.js chat + voice input (separate UI task).
7. Tests: retrieval assembly + confidence + role/PII gating on L0 deps (stub LLM, in-memory graph).

📝 Level 3 note: build retrieval on the in-memory `GraphModel` first (works with no DB, testable), then add the Neo4j-backed path behind the same interface.

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
