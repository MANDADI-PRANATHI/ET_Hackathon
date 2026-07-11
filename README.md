# Unified Asset & Operations Brain
ET AI Hackathon 2026 · Problem Statement #8 — Industrial Knowledge Intelligence

See **[PLAN.md](PLAN.md)** for the full plan and **[CLAUDE.md](CLAUDE.md)** for the
engineering guide. Everything runs locally and free.

**Documentation:** [User Guide](docs/USER_GUIDE.md) — for plant staff, how to use
every tab · [Admin & Developer Guide](docs/ADMIN_GUIDE.md) — configuration, data
onboarding, endpoints, the full internal pipeline, troubleshooting.

## Production setup — a real deployment, with real documents

This is the path for actually running the product against a real plant's
documents, with the graph persisted in a real database.

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/)
(free) and Python 3.11+.

```bash
# 1. Configure — pick ONE language-model path (or leave both blank; the
#    product still answers correctly, just without a polished paragraph):
cp .env.example .env
#   -> Online (Gemini, free tier): paste a key from https://aistudio.google.com/apikey
#      into GEMINI_API_KEY= in .env
#   -> Offline (Ollama, runs on your own machine): set LLM_PROVIDER=ollama in
#      .env — see "Going fully offline" below for which models to pull

# 2. Python environment + dependencies
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Start the database layer (Neo4j for the persisted graph, Postgres, MinIO)
make up
make init          # create the Neo4j schema from the ontology
make verify        # health-check every service + the LLM

# 4. Add your real documents
#    Drop files under data/corpus/<folder>/ — work_orders/, inspections/,
#    incidents/, permits/, regulations/, manuals/, procedures/,
#    operating_instructions/, emails/, drawings/, project_files/,
#    quality_records/. Supported: .csv .tsv .txt .md .eml .pdf .docx .xlsx
#    .pptx and images (P&IDs). Full folder-by-folder guide:
#    docs/ADMIN_GUIDE.md.

# 5. Ingest + build the graph
make ingest            # structured + regex + AI prose extraction
make build-graph       # merge into the asset-centric graph, load into Neo4j

# 6. Run it
make api                # http://localhost:8000/ui  ·  API docs at /docs
```

Re-running steps 4–5 after adding more documents is safe — merging is
idempotent, nothing gets duplicated. Neo4j's own browser is at
http://localhost:7474 if you want to inspect the graph directly with Cypher.

## Try it first — quick local demo (no Docker, no real documents needed)

Before committing to the production setup, you can see the whole product
working in under a minute:

```bash
python run.py --demo
```
`--demo` generates a full **synthetic** sample plant (fake work orders,
inspections, incidents, a planted overdue-inspection gap, everything the UI
needs to demo) and launches the app — no Docker, no database, no API key.
**This is for trying the product only — never use `--demo` for real data.**

```bash
python run.py
```
Without `--demo`, nothing fake is generated. This reads whatever real
documents you've already dropped into `data/corpus/` and launches the app the
same way. If `data/corpus/` is empty it tells you so and stops — it will not
silently show you fake data.

```bash
make test         # regression tests
make scorecard    # every judged metric, computed live
```

## 🔌 Runs fully offline — the LLM is optional
The system's core intelligence — finding the right evidence, connecting it
across departments, and every agent's verdict — runs on **plain code**, not a
cloud API. No local ML models to download either: retrieval is plain keyword
search, deliberately kept simple (see "Why keyword search, not embeddings?" in
[CLAUDE.md](CLAUDE.md) for the reasoning):

| Capability | Needs a cloud call? | Runs on |
|---|---|---|
| Structured data, tags, dates, reg-refs | **No** | plain code + regex |
| Finding & ranking the right evidence | **No** | keyword search (BM25) |
| Compliance verdict, RCA trends, confidence score | **No** | plain code |
| Answer composed with no LLM configured | **No** | local template over cited evidence |
| Prose extraction, drawing reading, final narrative | Optional | cloud LLM **or** a local model via Ollama |

With no API key at all, the system still gives cited, confidence-scored
answers — the cloud/local model only adds a polished paragraph on top. See the
in-app **"Help"** tab for the live version of this table, and
[CLAUDE.md](CLAUDE.md) for why this matters for plants that legally can't send
data to a foreign cloud.

### Going fully offline — local models via Ollama (optional, not downloaded for you)

If you want the polished narrative and drawing-reading to run on your own
machine instead of the cloud, install [Ollama](https://ollama.com/download)
and pull two models — balanced, mid-size (7B) so they run on a normal laptop
CPU/GPU without needing a data-center card, and strong for this specific job
(structured extraction / reading text off an image) rather than the biggest
model available:

| Job | Model | Pull | Size | Model page |
|---|---|---|---|---|
| Text — answers, compliance-rule authoring, RCA/warning narratives | **Qwen 2.5 7B Instruct** | `ollama pull qwen2.5:7b` | ~4.7 GB | [ollama.com/library/qwen2.5](https://ollama.com/library/qwen2.5) |
| Vision — reading tags off drawings/P&IDs | **Qwen 2.5-VL 7B** | `ollama pull qwen2.5vl:7b` | ~6 GB | [ollama.com/library/qwen2.5vl](https://ollama.com/library/qwen2.5vl) |

Why these two, specifically:
- **Qwen2.5:7b** — best structured-output reliability (JSON-schema-fenced facts,
  rule authoring) at a size that doesn't need a big GPU; smaller (3B-class)
  models miss fields noticeably more often in our extraction path.
- **Qwen2.5-VL:7b** — one of the strongest open vision-language models at this
  size specifically for *reading printed text/labels in an image*, which is
  exactly what tag-reading off a P&ID needs (validated end-to-end on a
  synthetic test drawing — 7/7 tags read correctly, see `eval/vision_probe.py`).

Then just flip one switch:
```bash
# in .env
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_VISION_MODEL=qwen2.5vl:7b
```
Nothing else changes — same endpoints, same UI, same citations. This swap has
not been run live in this project yet (see CLAUDE.md's known limitations); the
Gemini cloud path has been the one exercised end to end so far.

**Want to stress-test the demo with a large plant?** The synthetic sample size
scales (only relevant with `--demo` / `generate_synthetic.py` — never used
against real documents):
```bash
SCALE=50  python scripts/generate_synthetic.py    # ~400 assets, 4k work orders (default)
SCALE=200 python scripts/generate_synthetic.py    # a huge plant
SCALE=0   python scripts/generate_synthetic.py    # canonical demo assets only
```
The canonical demo assets (incl. the overdue PSV-110B) are always included, so
the benchmarks stay valid at any scale. The UI's **"Help"** tab explains the
pipeline — why this is a knowledge graph + rule engine, not an API wrapper.

---

## Want to go deeper?

If you want to run one pipeline stage at a time, see every `make` target
explained, or just see the project layout — that's all in the
**[Admin & Developer Guide](docs/ADMIN_GUIDE.md)**, clearly marked optional.
See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the architecture diagram.
