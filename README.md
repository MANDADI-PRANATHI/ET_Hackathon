# Unified Asset & Operations Brain
ET AI Hackathon 2026 · Problem Statement #8 — Industrial Knowledge Intelligence

See **[PLAN.md](PLAN.md)** for the full plain-English plan. This README covers
**Level 0 — the foundation**: infrastructure, the ontology, the provider switch,
and a synthetic data generator. Everything runs locally and free.

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

## Project layout
```
config/ontology/oil_and_gas.yaml   the asset-centric vocabulary (swap to change industry)
src/brain/config.py                all settings (reads .env)
src/brain/ontology.py              loads + validates the ontology
src/brain/providers/llm.py         Gemini / Ollama switch
src/brain/providers/embeddings.py  local embeddings + reranker (used from Level 1)
src/brain/stores/neo4j_init.py     creates the graph schema
scripts/verify_setup.py            health-check
scripts/generate_synthetic.py      synthetic plant records
data/corpus/                       the document corpus (by type)
```

Next: **Level 1 — read documents and extract facts.**
