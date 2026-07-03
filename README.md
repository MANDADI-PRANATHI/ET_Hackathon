# Unified Asset & Operations Brain
ET AI Hackathon 2026 · Problem Statement #8 — Industrial Knowledge Intelligence

See **[PLAN.md](PLAN.md)** for the full plan and **[CLAUDE.md](CLAUDE.md)** for the
engineering guide. This README covers **Level 0 (foundation)** and **Level 1
(read & extract)**. Everything runs locally and free.

---

## What Level 0 gives you
- **Local infrastructure** (Docker): Neo4j (connections + vector search), Postgres, MinIO — all $0.
- **The ontology** (`config/ontology/oil_and_gas.yaml`) — the asset-centric "vocabulary", swappable per industry.
- **The brain switch** (`src/brain/providers/llm.py`) — Gemini free tier *or* offline Ollama, one setting.
- **Schema setup** — Neo4j constraints + a vector index, generated from the ontology.
- **A synthetic corpus** — realistic work orders, inspections, permits, and non-conformances.
- **A health-check** that confirms everything is wired up.

---

## Prerequisites (one-time)
1. **Docker Desktop** (free) — https://www.docker.com/products/docker-desktop/  *(not yet installed on this machine)*
2. **Python 3.11+** — your current `python3` is 3.9; install 3.11 (e.g. `brew install python@3.11`) and use it below.
3. *(Optional, offline brain)* **Ollama** — https://ollama.com — then `ollama pull qwen2.5:7b`.

---

## Setup (run in order)
```bash
# 1. Configure
cp .env.example .env
#    -> if using Gemini: paste your free key from https://aistudio.google.com/apikey
#    -> if going offline: set LLM_PROVIDER=ollama in .env

# 2. Create a clean Python environment (use 3.11+)
python3.11 -m venv .venv && source .venv/bin/activate

# 3. Install Level 0 dependencies
make install

# 4. Start the databases
make up                # Neo4j UI: http://localhost:7474  · MinIO UI: http://localhost:9001

# 5. Create the graph schema (constraints + vector index) from the ontology
make init

# 6. Generate the synthetic plant records
make synth

# 7. Check everything is healthy
make verify
```

A passing `make verify` looks like:
```
[PASS] Ontology profile: oil_and_gas — 19 node types, 23 relationship types
[PASS] Neo4j: connected at bolt://localhost:7687
[PASS] Postgres: connected
[PASS] MinIO: bucket 'corpus' ready
[PASS] LLM provider: gemini responded 'ready'
```

---

## Add real documents
`make synth` fills the structured folders. Add real public PDFs (CSB incident
reports, OISD/OSHA regulations, OEM manuals, sample P&IDs) to the other folders
under `data/corpus/` — see **[data/corpus/SOURCES.md](data/corpus/SOURCES.md)**.
Reuse the asset tags listed there so everything links in the graph.

---

## Level 1 — read documents & extract facts
Turns the messy corpus into clean, **source-stamped, confidence-scored** facts,
staged as JSON for the graph build (Level 2).

```bash
make install-l1          # Level 1 deps (docling, embeddings) — for the full path
make ingest-structured   # structured + regex only (runs on Level 0 deps, no AI)
make ingest              # full: structured + regex + AI prose + embeddings
```

What it does, by the cheapest reliable method per fact:
- **Structured tables** (CSV work orders, inspections, permits, NCRs) → read
  straight into graph facts, no AI.
- **Predictable identifiers** (P-101A, OISD-STD-105, dates) → regex, no AI —
  with false-positive rejection for document references (INC-2026-014, etc.).
- **Prose** (incident reports, emails, SOPs) → the LLM extracts facts, each tied
  to its exact source sentence and capped below structured confidence.
- **Drawings / P&IDs** → a vision model reads the tags (needs-review before trust).

Every fact carries where it came from, how confident we are, and how it was found.
Output lands in `data/staging/*.json`.

**Measure it (judged metrics):**
```bash
python eval/extraction_eval.py     # entity-extraction accuracy (precision/recall/F1)
python -m pytest tests/ -q         # regression tests (Level 0 deps only)
```

## Level 2 — build the asset-centric knowledge graph
Merges the staged facts into one node per real thing and one edge per real
relationship, with the **asset as the hub**.

```bash
make build-graph          # merge + metrics + viz export, and load into Neo4j
```

- **Cross-document merge**: an asset named in ten documents becomes one node,
  its properties filled from the most trustworthy source (a table beats a guess).
- **Entity resolution done carefully**: variant surface forms collapse
  (`p-101a` → `P-101A`), but backup units stay separate — `P-101A` and `P-101B`
  are *not* merged. Unclear cases are *proposed* for review, never auto-merged.
- **Confidence builds up**: a fact confirmed by several documents scores higher.
- **Linkage completeness** (a judged metric) is reported per run, plus orphans
  and needs-review counts. A clean asset-centric graph is exported to
  `data/graph/graph_export.json` for the demo visualisation.

Re-running `make build-graph` is the **update path** — MERGE is idempotent, so
dropping in a new document, re-ingesting, and rebuilding folds it in without
duplication. (Runs fully without Neo4j: model, metrics, and export are always
produced; the database load is attempted when reachable.)

## Level 3 — the Ask-Anything Copilot (GraphRAG)
Answers plain-English questions using the graph **and** meaning-search together,
with clickable citations, a computed confidence, and role-aware framing.

```bash
make copilot Q="Is PSV-110B overdue for its statutory inspection?"   # CLI
make api                                                             # HTTP API (:8000/docs)
python eval/copilot_bench.py                                         # judged metrics
```

- **GraphRAG, not plain RAG**: spot the asset → pull its connected facts from the
  graph → add meaning-matched passages → answer. This is what lets a maintenance
  question be answered by a safety document (**cross-functional discovery**).
- **Confidence is computed** from extraction certainty, graph linkage, retrieval
  match, and multi-document agreement — a weak answer says so.
- **Every claim is cited** back to a source document (and page where known).
- **Role-aware** (technician / engineer / safety officer / auditor / operator),
  with personal data redacted for roles not cleared to see it.
- Runs over the merged graph from `data/staging` — **no Neo4j required**; works
  with the local embedder or a keyword fallback, and shows cited evidence even
  when no writer-LLM is configured.

Current benchmark (synthetic corpus): groundedness **1.0**, cross-functional
discovery **1.0**, asset-spotting **1.0** across 8 expert questions.

## Level 4a — Compliance & QMS agent
Maps regulations against real records and flags gaps — the yes/no decision made
by **exact code**, not the model.

```bash
make compliance          # evidence package + drafted non-conformances/CAPAs
python eval/compliance_eval.py    # gap-detection accuracy (precision/recall/F1)
```

- **Hybrid**: the LLM turns a regulation clause into a checkable rule
  (e.g. *valves → inspect every 182 days*); a plain-code checker compares it to
  the actual last-inspection dates in the graph → **met / gap / unknown**.
- Produces an **audit-ready evidence package** and auto-drafts a non-conformance
  and corrective action (CAPA) for every gap, each tied to its evidence.
- On the synthetic corpus it catches the planted gap — **PSV-110B, 57 days past
  its statutory limit** — and scores **1.0** gap-detection precision/recall/F1.

## Level 4b — Maintenance & RCA agent
Investigates *why* an asset failed by fusing its history with **recent operating
conditions**, and connects the dots no single team member can.

```bash
make rca ASSET=P-101A            # RCA report + predictive recs + optimised schedule
python eval/rca_eval.py          # RCA quality check
```

- Pulls work orders, inspections, failure modes and incidents from the graph and
  joins them with **live readings** through a small adapter — a replayed CSV for
  the demo; OPC-UA/MQTT plug into the *same* interface in a real plant.
- **Signals are computed by code** (a rising vibration trend, recent maintenance,
  an overdue inspection); the LLM only writes the narrative on top.
- On the synthetic corpus it catches P-101A's vibration climbing **2.4 → 7.2 mm/s
  (+200%)** before the trip, flags it as the top root cause, and recommends
  inspecting the bearing/seal before failure.

## Level 4c — Lessons-Learned & proactive warnings
Finds systemic patterns across the plant's history and **pushes warnings before
problems recur**.

```bash
make lessons                     # recurring patterns + prioritised warning feed
python eval/lessons_eval.py      # pattern/warning coverage check
```

- Mines the graph for **recurring findings**, **repeated failure modes**,
  **chronic repeated actions**, and **equipment-family clusters**.
- Fuses those patterns with live signals — **compliance gaps** and **rising
  trends** — into one prioritised warning feed (e.g. *PSV-110B overdue*,
  *P-101A vibration climbing*, *"inspection overdue" recurring across assets*).

## Level 5 — prove it & present it
```bash
make scorecard      # every judged metric, computed live, in one table
make api            # then open http://localhost:8000/ui  (mobile-first UI)
                    #   (or: python serve.py — no make needed, e.g. on Windows)
```

- **Live scorecard** maps straight onto the problem statement's evaluation focus
  — entity extraction, answer quality, graph linkage, compliance-gap detection,
  cross-functional discovery — computed from the running system, not claimed.
- **Mobile-first UI** (`web/index.html`, served at `/ui`): ask with voice, get
  cited + confidence-scored answers, browse the asset graph, and view the
  compliance / warnings / scorecard panels.
- **Generic engine**: swap the industry with one setting —
  `make verify ONTOLOGY_PROFILE=config/ontology/manufacturing.yaml`.

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the full architecture diagram.

## Project layout
```
config/ontology/oil_and_gas.yaml   the asset-centric vocabulary (swap to change industry)
src/brain/config.py                all settings (reads .env)
src/brain/ontology.py              loads + validates the ontology
src/brain/providers/llm.py         Gemini / Ollama switch
src/brain/providers/embeddings.py  local embeddings + reranker (used from Level 1)
src/brain/stores/neo4j_init.py     creates the graph schema
src/brain/schema.py                the staging data model (facts + chunks)
src/brain/ingest/                  Level 1: readers, patterns, extraction, pipeline
src/brain/search/keyword.py        BM25 baseline ("traditional search")
src/brain/graph/                   Level 2: merge model, resolution, metrics, export
src/brain/stores/graph_writer.py   persist the merged graph into Neo4j
src/brain/retrieval/knowledge.py   Level 3: GraphRAG retrieval
src/brain/copilot/                 Level 3: cited/confidence/role-aware answers
src/brain/agents/                  Level 4: compliance, RCA, lessons-learned
src/brain/stores/readings.py       readings adapter (time-series / OPC-UA-MQTT-shaped)
src/brain/api/app.py               FastAPI backend (/ask /graph /compliance /rca /warnings /scorecard)
web/index.html                     Level 5: mobile-first UI (served at /ui)
eval/scorecard.py                  Level 5: all judged metrics in one place
scripts/verify_setup.py            health-check
scripts/generate_synthetic.py      synthetic plant records + narrative docs
scripts/ingest.py                  Level 1 ingestion CLI
scripts/build_graph.py             Level 2 graph build CLI
eval/                              extraction benchmark (fixtures + labels + scorer)
tests/                             regression tests (Level 0 deps only)
data/corpus/                       the document corpus (by type)
```

Next: **Level 3 — the GraphRAG copilot.**
