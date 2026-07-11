# Sutradhar — Admin & Developer Guide

*How to run it, configure it, feed it data, and understand what's happening
under the hood. For the user-facing guide see [USER_GUIDE.md](USER_GUIDE.md);
for engineering conventions and design decisions see [../CLAUDE.md](../CLAUDE.md).*

---

## 1. Quick start

```bash
python run.py          # one command: checks deps, ingests the corpus, starts the API
# UI:  http://localhost:8000/ui/index.html
```

Or step by step:

```bash
pip install -r requirements.txt      # Level 0/1 deps (no torch, no GPU, ~small)
make synth                           # generate the synthetic demo corpus
make ingest-structured               # ingest without any AI (CSV + regex only)
make api                             # uvicorn brain.api.app:app
```

Nothing below is *required* for correct, cited answers: no Neo4j, no API key,
no internet. Each adds a layer when present.

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
| PDF ingestion fails | `docling` not installed (optional, heavy). Plain text/CSV paths are unaffected. |
| Drawings not ingested | The vision path needs a vision model and is skipped by upload/sync by design; use `make ingest` with a provider configured. |
| Neo4j connection errors on `build_graph` | Neo4j is optional — the API never needs it. Start it with `make up` only if you want persisted graph + Cypher access. |
| Uploaded file rejected (415) | Unsupported extension. Supported: .csv .tsv .txt .md .eml (+ .pdf/.docx with docling). |
