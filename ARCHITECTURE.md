# Architecture — Sutradhar, the Unified Asset & Operations Brain

ET AI Hackathon 2026 · Problem Statement #8. This is the architecture-diagram
deliverable; see [PLAN.md](PLAN.md) for the strategy and [CLAUDE.md](CLAUDE.md)
for the engineering guide.

---

## 1. One-screen overview

```
                         ┌──────────────────────────────────────────────┐
   Heterogeneous docs    │              INGESTION  (Level 1)              │
   PDFs · P&IDs · CSVs   │  router → readers → extraction → chunk         │
   emails · scans ──────▶│  structured(no AI) · regex · AI prose · vision │
                         │  every fact: source + confidence + extractor   │
                         └───────────────────────┬──────────────────────┘
                                                 │  data/staging/*.json  (StagedDoc)
                                                 ▼
                         ┌──────────────────────────────────────────────┐
                         │           KNOWLEDGE GRAPH  (Level 2)           │
                         │  merge by (label, canonical value) · resolve   │
                         │  entities (no over-merge) · confidence build-up│
                         │  ASSET is the hub · metrics · viz export       │
                         │        in-memory GraphModel  ──►  Neo4j        │
                         └───────────────────────┬──────────────────────┘
                                                 │  GraphModel + Chunk passages
                 ┌───────────────────────────────┼───────────────────────────────┐
                 ▼                               ▼                                 ▼
     ┌───────────────────────┐   ┌──────────────────────────┐   ┌──────────────────────────┐
     │  COPILOT (Level 3)    │   │   AGENTS (Level 4)        │   │  SCORECARD (Level 5)      │
     │  GraphRAG retrieval   │   │  4a compliance (hybrid)   │   │  every judged metric,     │
     │  = graph neighbourhood│   │  4b RCA + readings adapter│   │  computed live, 0 API     │
     │  + keyword search     │   │  4c lessons + warnings    │   │  calls                    │
     │  cited · confidence   │   │  code decides; LLM writes │   │  ontology-swap demo       │
     │  role-aware · PII gate │   │  the narrative (optional) │   │                           │
     └───────────┬───────────┘   └────────────┬─────────────┘   └────────────┬─────────────┘
                 └───────────────────┬─────────┴───────────────────┬─────────┘
                                     ▼                             ▼
                          FastAPI  (/ask /graph /compliance    Mobile-first UI (voice,
                          /rca /warnings /scorecard)           citations, graph, panels)
```

## 2. Layers and responsibilities

| Layer | Modules | Responsibility |
|---|---|---|
| **L0 Foundation** | `config`, `ontology`, `providers/llm`, `stores/neo4j_init` | Settings, swappable ontology, LLM provider, DB schema |
| **L1 Ingestion** | `ingest/{router,readers,patterns,extract,chunk,confidence,pipeline}` | Docs → source-stamped, confidence-scored facts (`StagedDoc`) |
| **L2 Graph** | `graph/{model,resolve,metrics,export}`, `stores/graph_writer` | Merge facts into the asset-centric graph; resolution; metrics; Neo4j |
| **L3 Copilot** | `retrieval/knowledge`, `copilot/{answer,roles}`, `api` | GraphRAG answers: cited, confidence-scored, role-aware |
| **L4 Agents** | `agents/{compliance,rca,lessons}`, `stores/readings` | Compliance/QMS, RCA + live conditions, lessons + proactive warnings |
| **L5 Prove/Present** | `eval/*`, `web/index.html` | Live scorecard, benchmarks, mobile UI, ontology-swap demo |

## 3. The spine: one fact model, three shapes

Every document yields a `StagedDoc` of **NodeFact / EdgeFact / Chunk**, and every
node/edge carries `source` (→ citation), `confidence`, and `extractor`
(`structured | regex | ai | vision`). Level 2 merges nodes by `(label, canonical
value)`; it never needs to know how a fact was found. This single contract is
what makes the system auditable end-to-end.

## 4. Design principles (enforced in code)

1. **Asset-centric** — every fact links back to an equipment tag; the hub is
   what enables cross-functional discovery.
2. **Cheapest reliable extractor wins** — tables read by code, identifiers by
   regex, prose by the LLM (schema-fenced), drawings by vision. AI never does
   what deterministic code does better.
3. **Confidence is built, not guessed** — extraction → linkage → retrieval →
   agreement, blended into the number the user sees.
4. **Hybrid agents** — the LLM reads and writes; **plain code decides** (a
   compliance verdict, a trend, a schedule). Verdicts are defensible.
5. **Everything behind a switch** — LLM provider, industry ontology, storage —
   swap without touching call sites.
6. **Degrade gracefully** — no API key, no Neo4j, no optional dep must break a
   path that doesn't need it. The whole product runs offline from `data/staging`.
7. **Plain code first, cloud last** — retrieval (graph traversal + keyword
   search), every agent verdict, and confidence scoring run with zero API
   calls or ML models. The cloud/local LLM only adds narrative polish; the
   copilot composes a genuinely readable answer from the same cited evidence
   when none is configured. A hybrid embeddings+reranker retrieval stack was
   built and benchmarked, found to make no measurable difference over plain
   keyword search on this system's own eval, and removed — see CLAUDE.md's
   "Why keyword search, not embeddings?" section for the full reasoning.

## 5. Storage

- **Neo4j** — the connections store (asset-centric graph). A vector-index
  schema stub exists for a future semantic-search path but is unused by the
  current retrieval, which runs entirely in-memory. For the demo the merged
  graph lives in an in-memory `GraphModel`, so the copilot and agents run
  without a database.
- **Postgres** — app state + the time-series readings table (via the readings
  adapter).
- **MinIO** — raw document storage (S3-compatible).

## 6. Retrieval — keyword search + GraphRAG

```
question ─▶ spot asset(s)  ─▶ graph neighbourhood (work orders, inspections,     ┐
              (tag/name/       incidents, procedures, regulations)              │
               class)                                                          ├─▶ combine ─▶ LLM (optional) ─▶ cited,
                                                                                │      or local extractive       confidence-scored
          ─▶ keyword search (BM25) over document passages ────────────────────  ┘      template over the         role-aware answer
                                                                                        same evidence
```

Graph + keyword search together are what let a maintenance question be
answered by a safety document — measured as the **cross-functional discovery
rate**. Most of an answer's correctness comes from the graph step (an exact
lookup of everything connected to the named asset); passage search is a
secondary layer, and plain keyword matching was measured to be sufficient for
it (see CLAUDE.md). The LLM box is optional by construction: with none
configured (or a failed call), the answer falls back to a deterministic,
role-framed composition built from the exact same cited evidence
(`Answer.mode == "extractive"`) instead of degrading to an error. Retrieval
quality, evidence selection, and confidence are therefore never a function of
API availability.

## 7. Evaluation mapping (the scorecard)

| PS evaluation focus | Metric source | Result* | Needs an API call? |
|---|---|---|---|
| Entity extraction accuracy | `eval/extraction_eval` | F1 1.0 | No |
| Query answer quality | `eval/copilot_bench` (groundedness) | 1.0 | No |
| Knowledge-graph linkage completeness | `graph/metrics` | 1.0 (at 408-asset scale) | No |
| Time-to-answer vs traditional search | `copilot_bench` (GraphRAG vs raw keyword) | measured | No |
| Compliance-gap detection accuracy | `eval/compliance_eval` | F1 1.0 | No |
| RCA / lessons-learned quality | `eval/rca_eval`, `eval/lessons_eval` | 1.0 / 1.0 | No |
| Cross-functional knowledge discovery | `eval/copilot_bench` | 1.0 | No |

\*On the demo corpus (408 assets, 6,257 passages incl. real CSB/OSHA
references); `make scorecard` recomputes every row live, with zero network
calls. **Caveat worth stating plainly**: these benchmark questions were
authored by the same person who built the system, so a "1.0" score means the
pipeline behaves as designed — it is not independent evidence of
generalization to questions nobody anticipated.

## 8. Generic engine, swappable industry

The engine is industry-agnostic; the **only** industry-specific file is the
ontology profile. `config/ontology/oil_and_gas.yaml` and
`config/ontology/manufacturing.yaml` share identical node/relationship *types*
(so all code runs unchanged) and differ only in vocabulary (asset classes, tag
shapes, regulations). Swap with one setting:

```
make verify ONTOLOGY_PROFILE=config/ontology/manufacturing.yaml
```

## 9. Validated on real industrial documents

Alongside the synthetic plant, the corpus includes real, publicly citable
material: two U.S. Chemical Safety Board investigation summaries (Honeywell
Geismar heat-exchanger rupture, Jan 2023; BP-Husky Toledo relief-valve/SIS
failure, Sep 2022) and the actual text of OSHA 29 CFR 1910.119(j) (mechanical
integrity — inspection, documentation, and deficiency-correction requirements).
Every fact in those documents traces to a real, named public source rather
than being synthesised, directly addressing the brief's "ideally validated
with real industrial document samples" evaluation note.
