# TODO / Task Tracker — Unified Asset & Operations Brain

Living task tracker for session handoff. Update on every meaningful change.
Plan of record: [PLAN.md](PLAN.md). Engineering guide: [CLAUDE.md](CLAUDE.md).

Legend: ✅ done · 🔄 in progress · ⏳ pending · 📝 decision · ⚠️ limitation

---

## Level status
- ✅ **Level 0 — Foundation** (infra, ontology, provider switch, schema, synth data, health-check)
- ✅ **Level 1 — Read & extract** (router, readers, deterministic + AI extraction, chunking, embeddings hook, benchmark, keyword baseline)
- ✅ **Level 2 — Knowledge graph build** (in-memory merge model, entity resolution, Neo4j writer, metrics, viz export, idempotent re-ingest)
- 🔄 **Level 3 — GraphRAG copilot** — backend DONE (retrieval, confidence, citations, role-aware, PII gating, API, benchmark); mobile UI + voice PENDING
- ✅ **Level 4a — Compliance & QMS agent** (hybrid rule engine, evidence package, NCR/CAPA drafting, gap-detection benchmark 1.0)
- ✅ **Level 4b — Maintenance & RCA agent** (readings adapter, trend detection, RCA fusion, predictive rec, optimised schedule; eval 1.0)
- 🔄 **Level 4c — Lessons-learned & proactive warnings** — NEXT
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

## Level 3 — backend DONE (detail)
- ✅ `retrieval/knowledge.py` — GraphRAG KnowledgeBase over in-memory graph: `spot_assets` (tag/name/class-synonym, precise queries stay precise), `asset_facts` (cited graph evidence), `search_passages` (embeddings cosine or keyword fallback), `retrieve` (combined).
- ✅ `copilot/answer.py` — cited answers, computed confidence (extraction+linkage+retrieval+agreement blend + label), honest "don't know", LLM injected.
- ✅ `copilot/roles.py` — role framing (technician/engineer/safety_officer/auditor/operator) + PII gating (redacts Person for non-cleared roles, incl. citation snippets).
- ✅ `scripts/copilot.py` CLI + Makefile `copilot`; `api/app.py` FastAPI (/ask,/graph,/roles,/health) + `install-l3`, `api` targets.
- ✅ `eval/copilot_bench.py` + `benchmark_questions.json` — groundedness 1.0, cross-functional discovery 1.0, asset-spotting 1.0 (8 questions).
- ✅ `tests/test_level3.py` — 7 tests (32 total).

## 🔄 Level 3 UI — PENDING (do after Level 4a or alongside Level 5)
- Mobile-first chat consuming POST /ask; render answer + confidence badge + clickable citations + cross-functional flag.
- Voice input via Web Speech API (field technicians).
- Graph visualisation from GET /graph.
- 📝 Decision: build as a self-contained HTML/JS single-page app served by FastAPI (static) rather than a full Next.js toolchain — mobile-responsive, voice-capable, far less fragile for the demo, and verifiable. Note Next.js as an alternative.

## Level 4a — DONE (detail)
- ✅ `agents/compliance.py` — RegRequirement model, curated RULESET (OISD-STD-105 valve 182d / vessel 365d), plain-code `check_requirement` (MET/GAP/UNKNOWN by exact date math — LLM never decides), `run_compliance`, `ComplianceReport.to_markdown()` evidence package + `.drafts()` NCR/CAPA. `parse_clause` (LLM-authored rules, injected, offline-safe fallback to RULESET).
- ✅ `scripts/compliance.py` + Makefile `compliance`; `/compliance` API endpoint.
- ✅ `eval/compliance_eval.py` — self-contained scenario, gap-detection precision/recall/F1 = 1.0.
- ✅ `tests/test_level4a.py` — 6 tests (38 total). Verified: PSV-110B caught GAP (239>182d, +57 overdue) with evidence + drafted NCR-AUTO/CAPA-AUTO.
- ⚠️ Threshold checks (parameter vs setpoint) stubbed until Level 4b readings land.
- ⚠️ Reg→RegRequirement→Asset graph edges not yet written back (report stands alone); optional polish.

## Level 4b — DONE (detail)
- ✅ `stores/readings.py` — ReadingsSource protocol + FileReadingsSource (CSV replay) + `analyze` (deterministic trend/rising detection). OPC-UA/MQTT implement the same interface in production.
- ✅ `agents/rca.py` — fuses graph history (work orders/inspections/failure modes/incidents) + readings; ranked findings (condition/failure_mode/maintenance), predictive recommendation, optimised schedule (statutory interval + criticality PM cadence); LLM narrative optional (template fallback).
- ✅ Synthetic readings generator (P-101A vibration 2.4→7.2 mm/s rising before the trip; P-101B flat control).
- ✅ `scripts/rca.py` + Makefile `rca`; `/rca/{asset}` API endpoint; `eval/rca_eval.py` score 1.0.
- ✅ `tests/test_level4b.py` — 4 tests (42 total).
- ⚠️ Output strings use ASCII (`->`) to stay safe on Windows consoles; markdown files are utf-8.

## 🔄 Level 4c — NEXT (immediate actions)
1. `agents/lessons.py` — mine graph history (incidents, near-misses, audit findings, non-conformances) for recurring patterns (same failure mode across assets, repeated finding types, asset families with clustered issues).
2. Proactive warnings: match a current asset's condition/history against past patterns → push a warning (alert feed) before recurrence. Deterministic pattern-match core + optional LLM phrasing.
3. `scripts/lessons.py` + Makefile target; `/warnings` API endpoint; `eval/lessons_eval.py`; tests.

## Then: Level 3 UI + Level 5
- Self-contained mobile-first HTML/JS UI (served by FastAPI static) hitting /ask,/graph,/compliance,/rca,/warnings; voice via Web Speech API; graph viz.
- Level 5: unified `scorecard` aggregating every eval JSON (extraction, copilot, compliance, rca, lessons) into one command + a dashboard tile; ontology-swap demo; ARCHITECTURE.md + diagram; deck/demo notes.

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
