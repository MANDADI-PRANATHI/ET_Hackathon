# Sutradhar — Admin & Developer Guide

*How to run it, configure it, feed it data, and understand what's happening
under the hood. For the user-facing guide see [USER_GUIDE.md](USER_GUIDE.md);
for engineering conventions and design decisions see [../CLAUDE.md](../CLAUDE.md).*

---

## 1. Quick start

```bash
python run.py --demo    # generates a fake synthetic sample plant, then launches
                        # (for trying the product only — never for real data)
python run.py           # real use: reads whatever's already in data/corpus/,
                        # generates nothing fake; tells you if there's nothing
                        # to read yet
# UI:  http://localhost:8000/ui/index.html
```
This is genuinely enough, including for real use — no Docker, no database
required. The README's primary path is now Docker (`make docker-app` /
`docker-ollama` / `docker-neo4j` / `docker-both`); this local path is the
alternative for development or if you don't want Docker at all.

**Document reading is three tiers, cheapest first (see
`src/brain/ingest/readers/document.py`):**

1. **Light, always installed, no AI** — `pypdf`/`python-docx`/`python-pptx`/
   `openpyxl` (`requirements-l0.txt`) read born-digital `.pdf`/`.docx`/`.xlsx`/
   `.pptx` (real embedded text, not a scan) directly.
2. **Vision-model fallback for a scanned PDF page** — a scanned page has no
   embedded text layer, but a photo of a page *is* an image, so if step 1
   finds under 40 characters and a vision-capable LLM is already configured
   (Gemini, or Ollama via `make docker-ollama`/`docker-both`), the page is
   rendered to an image (`pymupdf`, lightweight — no ML weight itself) and
   read the same way a drawing/P&ID is read. No extra install if you already
   have a vision model configured for anything else. Facts from this tier are
   stamped `extractor=vision`, confidence 0.5, `needs_review=True` — same
   treatment as a drawing, verified via `ingest_file()` on a synthetic
   image-only PDF.
3. **Docling — the true last resort**, only reached for legacy `.doc`/`.xls`/
   `.html`, or a scanned PDF when *no* vision model is configured at all (tier
   2 has nothing to call): locally, run `python run.py --full` once to
   install it and ingest; in Docker, build with
   `INSTALL_PDF=true docker compose build app` (not one of the four primary
   commands — see `requirements-pdf.txt` for why: it pulls in `torch`/
   `transformers`, several GB, for layout analysis + OCR that tier 1/2
   usually make unnecessary).

Vision calls are capped at 5 pages per scanned PDF (`_MAX_VISION_PAGES` in
`document.py`) to protect free-tier quota (Gemini: 20 req/day) — a large
scanned document will only have its first 5 pages read this way.

Or step by step:

```bash
pip install -r requirements.txt      # everything needed (no torch, no GPU)
make synth                           # generate the SYNTHETIC demo corpus (fake data)
make ingest-structured                # ingest without any AI (CSV + regex only)
make api                              # uvicorn brain.api.app:app
```

Nothing above is *required* for correct, cited answers: no Neo4j, no API key,
no internet. Each adds a layer when present.

**Running the local LLM manually (outside Docker):** install
[Ollama](https://ollama.com/download), then pull two balanced, mid-size (7B)
models — chosen over bigger ones (no data-center GPU needed) and smaller ones
(miss fields in structured extraction):
```bash
ollama pull qwen2.5:7b       # text — answers, compliance-rule authoring, RCA narratives
ollama pull qwen2.5vl:7b     # vision — reading tags off drawings/P&IDs
```
Then in `.env`: `LLM_PROVIDER=ollama`. (`make docker-ollama` does all of this
automatically inside a container instead, if you're using Docker.)

**Stress-testing with a larger synthetic plant** (`--demo` / `make synth` only
— never used against real documents):
```bash
SCALE=50  python scripts/generate_synthetic.py    # ~400 assets, 4k work orders (default)
SCALE=200 python scripts/generate_synthetic.py    # a huge plant
SCALE=0   python scripts/generate_synthetic.py    # canonical demo assets only
```

## 2. Configuration (`.env`)

| Variable | Default | What it does |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | `gemini` (cloud) or `ollama` (fully local). Only affects prose polish + AI extraction. |
| `GEMINI_API_KEY` | — | Enables the cloud LLM. Missing → extractive answers (still cited + scored). |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Cloud model name. |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | localhost / llama3.1 | Local LLM via Ollama (code-complete, not yet exercised live). |
| `ONTOLOGY_PROFILE` | `config/ontology/oil_and_gas.yaml` | The industry vocabulary — swap to `manufacturing.yaml` and node classes, tag patterns AND compliance rules change with it. |
| `STAGING_DIR` | `data/staging` | Where ingested facts (JSON) live. The API builds its in-memory graph from here at startup. |
| `CORPUS_DIR` | `data/corpus` | The document folder `/upload` and `/sync` operate on. Point it at a OneDrive/SharePoint-synced folder for automatic enterprise onboarding. |
| `READINGS_FILE` | `data/readings/readings.csv` | Sensor-readings replay file for RCA/warnings trend detection. |
| `NEO4J_URI` etc. | localhost | Optional persistence. The runtime path is the in-memory graph; Neo4j write is best-effort. |

## 3. Getting data in

### Corpus folder layout (folder name = document type)
```
data/corpus/
  project_files/      asset registers, datasheets (CSV/TXT)
  work_orders/        CMMS exports (CSV) or free-text notes
  inspections/        inspection reports
  permits/            work permits
  quality_records/    NCRs, CAPAs
  incidents/          incident / near-miss reports
  regulations/        regulation text (drives compliance rule authoring)
  manuals/ procedures/ operating_instructions/ emails/ drawings/
```

### Four onboarding paths
1. **Full ingest** (first time / bulk): `make ingest-structured` (no AI) or
   `make ingest` (adds LLM prose extraction; needs a key or Ollama).
2. **UI upload** — Connect knowledge tab → ingested live, brain refreshes in place.
3. **Folder sync** — `POST /sync` (or the UI button): incremental — only files
   whose mtime is newer than their staged JSON are re-read.
4. **REST push** — any script/CMMS job:
   ```bash
   curl -X POST "http://host:8000/upload?filename=wo.csv&folder=work_orders" \
        --data-binary @wo.csv
   ```

CSV tables are recognised by their column signature (see
`src/brain/ingest/readers/structured.py`) — asset registers, work orders,
inspections, permits, non-conformances. Unrecognised tables still become
searchable text. Live upload/sync uses deterministic extractors only (fast,
offline); run `make ingest` when you want the AI prose-extraction pass too.

## 4. How it works (5-minute version)

```
corpus files -> ingest -> data/staging/*.json -> in-memory GraphModel -> API
               (route -> read -> extract -> chunk)     (merge + entity resolution)
```

- **Every fact carries source + confidence + extractor** (structured 1.0,
  regex 0.9, ai ≤0.85, vision 0.5+review). Level 2 merges facts by
  (label, value) with property precedence by extractor trust.
- **Retrieval** = graph traversal (spot the asset tag in the question, pull all
  its connected facts) + BM25 keyword search over passages. No embeddings — a
  hybrid embeddings/reranker stack was built, benchmarked, found to change
  nothing on our eval, and removed (full story in CLAUDE.md).
- **Answers**: the LLM writes prose when reachable; otherwise
  `_extractive_answer` composes the same cited evidence locally.
  `Answer.mode` tells you which happened.
- **Agents** decide with plain code (date math, status checks, trend slopes);
  the LLM only authors rules from regulation text and narrates.

## 5. Endpoints

| Endpoint | What it does |
|---|---|
| `GET /health` | What's actually loaded (assets, chunks, llm_ready). |
| `POST /ask` | `{question, role}` → cited, scored answer. |
| `GET /assets` · `GET /assets/{tag}/summary` · `GET /assets/{tag}/timeline` | Asset list / dashboard header / chronological history. |
| `GET /graph?asset=TAG` | Asset-centric subgraph for visualisation. |
| `GET /compliance` | Full compliance run + evidence package + NCR/CAPA drafts. |
| `GET /rca/{asset}` | Root-cause findings, trends, recommendations, schedule. |
| `GET /warnings` | Proactive warnings + recurring patterns. |
| `GET /scorecard` | Live self-evaluation metrics. |
| `POST /upload` · `POST /sync` | Live document onboarding (section 3). |

## 6. Editing compliance rules

Rules live in the ontology profile itself (`compliance_rules:` section of
`config/ontology/*.yaml`) — that's what makes the industry swap real. Example:

```yaml
compliance_rules:
  - id: REQ-OISD105-VALVE-INSP
    code: OISD-STD-105
    applies_to_class: Valve
    check_type: interval_days      # or: no_open_nonconformance | record_exists
    interval_days: 182
    description: "6-month inspection cycle for relief valves."
```

Three check types, all decided by plain code: `interval_days` (date math
against the latest linked Inspection), `no_open_nonconformance` (open NCR
linked via RAISED_AGAINST → GAP), `record_exists` (asset must have a linked
node of `requires_label`). New rules can also be authored from regulation
prose by the LLM (`parse_clause`) — but the *verdict* is never the LLM's.

## 7. Testing & evaluation

```bash
python -m pytest tests/ -q        # 60+ tests, no Neo4j/LLM/docling needed, <1 min
python eval/extraction_eval.py    # entity-extraction accuracy vs labels
python eval/copilot_bench.py      # answer groundedness / cross-functional discovery
python eval/compliance_eval.py    # gap detection vs ground truth
```

Honest caveat: the benchmark questions are self-authored. Treat scores as "the
pipeline works as designed", not independent validation.

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Answers say "local mode" | LLM unreachable (no key, no internet, or 429 quota). Not an error — facts/citations unaffected. Gemini free tier: 20 req/day; 429s are retried ~3× with backoff, then fall back. |
| `/compliance` empty after switching ontology profile | The staged corpus is from another industry — the new profile's asset classes don't exist in it. Ingest a corpus for that industry. |
| PDF ingestion fails | Normal `.pdf .docx .xlsx .pptx` read directly, no addon. A scanned page falls back to the vision model already configured (Gemini/Ollama) — only fails if *neither* that *nor* Docling (optional, heavy) is available. |
| Drawings not ingested | The vision path needs a vision model and is skipped by upload/sync by design; use `make ingest` with a provider configured. Validated once on a synthetic P&ID (`python eval/vision_probe.py`, 7/7 tags read) — a real scanned drawing is untested. |
| Neo4j connection errors on `build_graph` | Neo4j is optional — the API never needs it. Start it with `make docker-neo4j` only if you want persisted graph + Cypher access. |
| Uploaded file rejected (415) | Unsupported extension. Supported: .csv .tsv .txt .md .eml .pdf .docx .xlsx .pptx (+ legacy .doc/.xls/.html with the Docling addon). |

---

## Appendix: the full pipeline, stage by stage (for developers/judges who want to see how it works internally)

For the optional Docker/Neo4j persistence setup, see "Setup — Docker, one
command" in the README. This appendix is for running one pipeline stage at a
time or inspecting its output; the internal stage names ("Level 1", "Level
2"...) are engineering shorthand from how this was built and don't mean
anything is missing if you never see them.

### Stage by stage
| Stage | What it does | Command |
|---|---|---|
| Ingest | Corpus files → source-stamped, confidence-scored facts (tables/regex, no AI; prose optionally via LLM) | `make ingest-structured` (no AI) or `make ingest` (adds AI prose extraction; needs `--full`'s deps) |
| Graph build | Merge staged facts into one asset-centric graph; entity resolution; metrics + viz export | `make build-graph` (loads into Neo4j if reachable; the model/metrics/export always run without it) |
| Ask (copilot) | GraphRAG: graph traversal + keyword search → cited, confidence-scored, role-aware answer | `make copilot Q="..."` (CLI) or `make api` (HTTP) |
| Compliance | LLM authors a checkable rule from regulation text; plain code decides MET/GAP | `make compliance` |
| RCA | Fuse graph history + live readings into ranked root-cause findings | `make rca ASSET=P-101A` |
| Lessons/warnings | Mine recurring patterns; push a prioritised warning feed | `make lessons` |
| Scorecard | Every judged metric, computed live | `make scorecard` |

Benchmarks per stage: `python eval/extraction_eval.py`, `eval/copilot_bench.py`,
`eval/compliance_eval.py`, `eval/rca_eval.py`, `eval/lessons_eval.py` — or
`python -m pytest tests/ -q` for the full regression suite.

### Adding real (non-synthetic) documents
`make synth` fills the structured folders with generated data. To add real
public PDFs (CSB incident reports, OISD/OSHA regulations, OEM manuals, sample
P&IDs), drop them under `data/corpus/<folder>/` — see
[data/corpus/SOURCES.md](../data/corpus/SOURCES.md) for the folder-to-doctype
mapping and reused asset tags. The corpus already ships with two real CSB
investigation summaries and the actual OSHA 29 CFR 1910.119(j) text, each
tracing to a citable public source.

Supported formats: `.csv`/`.tsv` (code, no AI) · `.txt .md .eml` (stdlib) ·
`.pdf .docx .xlsx .pptx` (light readers — `pypdf`/`python-docx`/`python-pptx`/
`openpyxl`, always installed, no AI) · a scanned PDF page (vision model, same
one configured for drawings — no extra install) · legacy `.doc .xls .html`,
or a scanned page with no vision model configured (Docling fallback —
`make install-l1`) · `.png .jpg .jpeg .tif .tiff .bmp` (drawings, via a
vision model). One unreadable file is skipped with a warning, never crashes
the batch. After adding files: `make ingest && make
build-graph` (MERGE is idempotent — no duplication on re-runs).

### Project layout
```
config/ontology/oil_and_gas.yaml   the asset-centric vocabulary (swap to change industry)
src/brain/config.py                all settings (reads .env)
src/brain/ontology.py              loads + validates the ontology
src/brain/providers/llm.py         Gemini / Ollama switch
src/brain/stores/neo4j_init.py     creates the graph schema
src/brain/schema.py                the staging data model (facts + chunks)
src/brain/ingest/                  readers, patterns, extraction, pipeline
src/brain/search/keyword.py        BM25 keyword search (also the passage-retrieval engine)
src/brain/graph/                   merge model, resolution, metrics, export
src/brain/stores/graph_writer.py   persist the merged graph into Neo4j
src/brain/retrieval/knowledge.py   GraphRAG retrieval (graph + keyword search)
src/brain/copilot/answer.py        cited/confidence/role-aware answers + extractive fallback
src/brain/agents/                  compliance, RCA, lessons-learned
src/brain/stores/readings.py       readings adapter (time-series / OPC-UA-MQTT-shaped)
src/brain/api/app.py               FastAPI backend (/ask /graph /compliance /rca /warnings /scorecard)
web/index.html                     mobile-first UI (served at /ui)
eval/                              benchmarks (extraction, copilot, compliance, rca, lessons, scorecard)
scripts/verify_setup.py            health-check
scripts/generate_synthetic.py      synthetic plant records (SCALE=N to grow it)
run.py                             one-command setup + launch
tests/                             regression tests (Level 0 deps only)
data/corpus/                       the document corpus (by type; includes real CSB/OSHA references)
```
