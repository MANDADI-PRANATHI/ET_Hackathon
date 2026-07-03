# TODO / Task Tracker — Unified Asset & Operations Brain

Living task tracker for session handoff. Update on every meaningful change.
Plan of record: [PLAN.md](PLAN.md). Engineering guide: [CLAUDE.md](CLAUDE.md).

Legend: ✅ done · 🔄 in progress · ⏳ pending · 📝 decision · ⚠️ limitation

---

## Level status
- ✅ **Level 0 — Foundation** (infra, ontology, provider switch, schema, synth data, health-check)
- ✅ **Level 1 — Read & extract** (router, readers, deterministic + AI extraction, chunking, benchmark, keyword baseline)
- ✅ **Level 2 — Knowledge graph build** (in-memory merge model, entity resolution, Neo4j writer, metrics, viz export, idempotent re-ingest)
- ✅ **Level 3 — GraphRAG copilot** (retrieval, confidence, citations, role-aware, PII gating, API, mobile UI + voice, benchmark)
- ✅ **Level 4a — Compliance & QMS agent** (hybrid rule engine, evidence package, NCR/CAPA drafting, gap-detection benchmark 1.0)
- ✅ **Level 4b — Maintenance & RCA agent** (readings adapter, trend detection, RCA fusion, predictive rec, optimised schedule; eval 1.0)
- ✅ **Level 4c — Lessons-learned & proactive warnings** (recurring patterns + multi-signal warning feed; eval 1.0)
- ✅ **Level 5 — scorecard, UI, ontology-swap demo, architecture doc** (all judged metrics aggregated; mobile UI with voice + graph + agent panels; manufacturing profile; ARCHITECTURE.md)
- ✅ **Post-L5 polish** (shadcn UI, one-command runner, scale-up, ingest hardening, real documents, extractive answer fallback) — see dedicated section below. A hybrid embeddings+reranker retrieval stack was also built in this window, benchmarked against plain keyword search, found to make no difference, and **stripped back out** — see "Retrieval simplified" below.

---

## Level 1 — DONE (detail)
- ✅ Staging data model `brain/schema.py` (NodeFact/EdgeFact/Chunk/StagedDoc, source+confidence+extractor).
- ✅ Deterministic extraction `ingest/patterns.py`: tag/reg/date regex, normalisation, priority-resolved non-overlapping matches, document-reference false-positive rejection.
- ✅ Chunking `ingest/chunk.py` (paragraph-aware, overlap, char spans).
- ✅ Confidence `ingest/confidence.py` (base per extractor, agreement boost, answer blend + labels).
- ✅ Readers: `structured` (CSV→facts, no AI), `text` (.txt/.eml), `document` (Docling, lazy), `drawing` (vision, injectable).
- ✅ Router `ingest/router.py` (folder→doc_type, ext→reader, stable ids).
- ✅ AI prose extraction `ingest/extract.py` (schema-fenced, evidence-quoted, confidence-capped, LLM injected).
- ✅ Pipeline `ingest/pipeline.py` + `scripts/ingest.py` (`--structured-only`, `--path`, `--ai`).
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
- ✅ `retrieval/knowledge.py` — GraphRAG KnowledgeBase over in-memory graph: `spot_assets` (tag/name/class-synonym, precise queries stay precise), `asset_facts` (cited graph evidence), `search_passages` (plain BM25 keyword search), `retrieve` (combined). A hybrid embeddings+reranker version of this was built, benchmarked, found to score identically, and removed — see "Retrieval simplified" below.
- ✅ `copilot/answer.py` — cited answers, computed confidence (extraction+linkage+retrieval+agreement blend + label), honest "don't know", LLM injected.
- ✅ `copilot/roles.py` — role framing (technician/engineer/safety_officer/auditor/operator) + PII gating (redacts Person for non-cleared roles, incl. citation snippets).
- ✅ `scripts/copilot.py` CLI + Makefile `copilot`; `api/app.py` FastAPI (/ask,/graph,/roles,/health) + `install-l3`, `api` targets.
- ✅ `eval/copilot_bench.py` + `benchmark_questions.json` — groundedness 1.0, cross-functional discovery 1.0, asset-spotting 1.0 (8 questions).
- ✅ `tests/test_level3.py` — 7 tests (32 total).

## Level 3 UI — DONE (see also "shadcn UI + scale + one-command" below)
- ✅ Mobile-first chat consuming POST /ask; confidence badge + clickable citations + cross-functional flag.
- ✅ Voice input via Web Speech API (field technicians).
- ✅ Graph visualisation from GET /graph (now per-asset, capped — see below).
- 📝 Decision: self-contained HTML/JS single-page app served by FastAPI (static) rather than a full Next.js toolchain — mobile-responsive, voice-capable, far less fragile for the demo, and verifiable. Next.js remains a drop-in upgrade path if ever needed.

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

## Level 4c — DONE (detail)
- ✅ `agents/lessons.py` — `find_patterns` (recurring findings, recurring failure modes, chronic repeated actions, equipment-family clusters) + `generate_warnings` combining compliance gaps + rising trends + recurring findings into a prioritised, de-duplicated feed. Deterministic core, optional LLM phrasing.
- ✅ `scripts/lessons.py` + Makefile `lessons`; `/warnings` API endpoint; `eval/lessons_eval.py` score 1.0; `tests/test_level4c.py` 5 tests (47 total).

## Level 5 — DONE (detail)
- ✅ `eval/scorecard.py` — aggregates every benchmark into one JSON + table, mapped to the PS evaluation focus; graceful "n/a" if inputs missing. Makefile `scorecard`; `/scorecard` API endpoint. Live result: extraction 1.0, groundedness 1.0, linkage 0.958, compliance 1.0, cross-functional 1.0, RCA 1.0, lessons 1.0.
- ✅ `web/index.html` — single-file mobile-first UI served by FastAPI at `/ui`: chat with confidence badge + clickable citations + cross-functional flag + role selector, **voice input** (Web Speech API), interactive graph (hub + neighbours), compliance / warnings / scorecard panels.
- ✅ Ontology-swap: `config/ontology/manufacturing.yaml` (same node/rel types, different vocabulary); `make verify ONTOLOGY_PROFILE=...` proves generality.
- ✅ `ARCHITECTURE.md` with diagrams (deliverable).
- ✅ `tests/test_level5.py` — scorecard aggregation + ontology interchangeability.
- ✅ `tests/test_api.py` — full HTTP surface smoke test (skips if FastAPI absent). **54 tests total.**
- ✅ API uses the modern lifespan handler (no deprecation warnings). Verified end-to-end via TestClient: /health, /ask (High 0.976, 17 cites, cross-functional), /compliance (1 GAP), /warnings, /rca, /graph, /scorecard, /ui.

## Post-L5: shadcn UI, one-command runner, scale-up, ingest hardening — DONE
- ✅ `web/index.html` rebuilt to a shadcn/ui design system: grey background, white
  cards, indigo primary + semantic success/warning/danger colours, Space
  Grotesk/IBM Plex Sans/IBM Plex Mono type pairing. Verified live on desktop +
  mobile across all tabs.
- ✅ `run.py` — one-command setup + launch (`python run.py`): installs minimal
  deps, generates data, ingests, opens the browser. `serve.py` +
  `.claude/launch.json` for the plain API-only path. No Docker/API key needed.
- ✅ `scripts/generate_synthetic.py` — `SCALE` env/`--scale` layers a large plant
  (default ~400 assets, 4k work orders, 750 permits, 500 NCRs, ~130 narrative
  docs, readings) on top of the byte-identical canonical demo assets. Verified
  at scale: 13k+ graph nodes, all scorecard metrics still 1.0.
- ✅ Graph visualisation fixed for scale: `graph/export.py::asset_subgraph` +
  `asset_list`; `/assets` + `/graph?asset=TAG&limit=N` return a capped,
  colour-coded-by-relationship-type neighbourhood instead of shipping the
  whole graph to the browser. Legend + tooltips; "showing N of M" when capped.
- ✅ "How it works" UI tab: 5-step pipeline (Ingest→Connect→Retrieve→Decide→
  Answer) with code-vs-AI tags, live stats, and — after the offline-first work
  below — a full "what needs a network call" capability table.
- ✅ Ingestion hardened: `ingest_corpus` wraps each file so one unreadable
  document is skipped with a warning (reports a `failed` count) instead of
  crashing the batch; drawing/vision files are skipped (not force-called) when
  `enable_vision=False` (the structured-only path).

## Retrieval simplified — built hybrid, measured it, removed it
Directive at the time: minimise dependence on Gemini; prefer fully local/
offline where it doesn't compromise quality. Built a hybrid retrieval stack
(BM25 + on-device embeddings, fused with Reciprocal Rank Fusion, reranked by a
local cross-encoder), an embedding-cache subsystem, and a local
"faithfulness" scorer. All of it worked. Then it was benchmarked against plain
keyword search on this project's own 8-question eval and **scored
identically — 1.0 groundedness, 1.0 cross-functional discovery, both ways.**

Given no measured quality gain, and given the real cost (~4 GB of downloaded
models, 20-30s startup delay, a caching subsystem that introduced its own bug
requiring its own fix, general code complexity out of proportion to a
hackathon judging window), **the whole stack was removed in a follow-up
session** and retrieval was reverted to plain keyword search. See CLAUDE.md's
"Why keyword search, not embeddings?" for the full reasoning, kept as a
standing decision record so nobody re-adds this complexity without first
re-running the benchmark.

**What was removed:**
- `src/brain/providers/embeddings.py` (LocalEmbedder/LocalReranker) — deleted.
- `src/brain/copilot/faithfulness.py` + `eval/faithfulness_eval.py` — deleted.
- `scripts/embed.py` + the `_carry_forward_embeddings()` cache-preservation
  logic in `ingest/pipeline.py` — deleted (the bug it fixed only existed
  because the cache it was protecting existed).
- `tests/test_embed_cache.py` — deleted (tested the now-gone cache).
- `tests/test_offline.py` — trimmed from 13 tests down to 3: kept the
  extractive-answer-fallback tests (that feature stays — it's pure code, no
  model, no dependency), removed the RRF-fusion/reranker/faithfulness tests.
- `sentence-transformers` + `transformers` packages uninstalled;
  `BAAI/bge-base-en-v1.5` + `BAAI/bge-reranker-base` model downloads deleted
  from the HuggingFace cache (~3.15 GB reclaimed). **`torch` was deliberately
  left installed** — it's required by other, unrelated software already on
  this machine (`ultralytics`, `stable_baselines3`, `torchvision`); removing
  it would have broken those, which was not this project's call to make.
- `EMBED_MODEL`/`RERANKER_MODEL` settings, `--embeddings` CLI flags, `make
  embed` target, and all UI copy referencing "hybrid search"/"reranker" —
  removed or corrected to describe plain keyword search accurately.
- `Answer.mode` (`"extractive"`/`"generative"`) **stays** — it's the one piece
  of that session's work that's pure code with zero dependency cost and
  genuinely useful (the copilot still answers, cited and confident, with no
  LLM configured or reachable).

**Result**: full test suite back to fast (~25-35s, no model loading), demo
behaviour and every scorecard number unchanged, `python run.py` launches in
~6s instead of ~25s+.

## Remaining / optional polish
- ⚠️ Presentation deck + demo video (deliverables) — outlines/notes in [DEMO.md](DEMO.md); not code.
- ⚠️ Neo4j-backed retrieval path (copilot currently uses the in-memory graph — sufficient for the demo; a Neo4jKnowledgeBase can implement the same surface for scale).
- ⚠️ Docling per-page citation precision.
- ⚠️ Reg→RegRequirement→Asset write-back so some regulations aren't graph orphans (compliance report already stands alone; not a correctness issue).
- ⚠️ Ollama vision/text path is code-complete and import-safe but not exercised against a live Ollama server in this environment (no local daemon/model-pull access here) — worth a real run before claiming it in a demo.

## How to run the whole thing
```
python run.py                                 # one command: setup + launch (see README)
# — or, layer by layer —
make up && make init && make synth            # infra + schema + synthetic corpus + readings
make ingest        (or make ingest-structured on L0 deps)
make build-graph                              # merge into the graph (+ Neo4j if up)
make api                                       # then open http://localhost:8000/ui
make scorecard                                 # every judged metric, live, 0 API calls
make test                                      # 57 tests, ~25-35s, Level 0 deps only, no ML models
```

---

## 📝 Key decisions
- Per-document staging; cross-document asset merge happens at Level 2 (keeps Level 1 stateless & parallelisable).
- Structured facts = confidence 1.0; regex = 0.9; AI ≤ 0.85; vision = 0.5 + needs_review. AI never outranks a table.
- Equipment-tag regex rejects hyphen-embedded refs and non-asset prefixes (WO/NCR/INC/SOP/…) to avoid bogus assets.
- Committed benchmark fixtures in `eval/fixtures` (stable, always runnable) — independent of the gitignored corpus.
- Real git commits per level (repo convention `feat(lN): …`) so sessions resume cleanly.
- **Plain code first, cloud LLM last** — retrieval (graph traversal + keyword search), agent verdicts, and confidence never require an API call; the LLM only polishes the narrative. See CLAUDE.md's "Why keyword search, not embeddings?" section for the full rationale, including the benchmark that led to removing a heavier retrieval stack.
- **Measure before keeping complexity.** A hybrid embeddings+reranker retrieval stack was built, benchmarked against the simpler alternative, found to make no difference, and removed. Any future "this would make it smarter" addition to retrieval should be justified the same way — a before/after run of `eval/copilot_bench.py`, not just a plausible-sounding argument.

## ⚠️ Known limitations
- Docling page-level char mapping not wired → PDF citations resolve to document, not page.
- AI + vision paths verified via stubs (unit tests) and, for the text LLM, live Gemini calls; vision (P&ID) and Ollama specifically are not yet exercised against real inputs in this environment.
- Benchmark scores in `eval/` are self-authored (same person wrote the system and the test questions) — "1.0" means "behaves as designed," not independent proof of generalization.
- Torch remains installed on this machine because other, unrelated software depends on it — it is **not** a dependency of this project anymore; nothing in `src/brain` imports it.
