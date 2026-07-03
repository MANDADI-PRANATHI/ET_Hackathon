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
scripts/verify_setup.py            health-check
scripts/generate_synthetic.py      synthetic plant records + narrative docs
scripts/ingest.py                  Level 1 ingestion CLI
scripts/build_graph.py             Level 2 graph build CLI
eval/                              extraction benchmark (fixtures + labels + scorer)
tests/                             regression tests (Level 0 deps only)
data/corpus/                       the document corpus (by type)
```

Next: **Level 3 — the GraphRAG copilot.**
