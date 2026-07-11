# Unified Asset & Operations Brain
ET AI Hackathon 2026 · Problem Statement #8 — Industrial Knowledge Intelligence

See **[PLAN.md](PLAN.md)** for the full plan and **[CLAUDE.md](CLAUDE.md)** for the
engineering guide. Everything runs locally and free.

**Documentation:** [User Guide](docs/USER_GUIDE.md) — for plant staff, how to use
every tab · [Admin & Developer Guide](docs/ADMIN_GUIDE.md) — configuration, data
onboarding, endpoints, the full internal pipeline, troubleshooting.

## Setup — one command. This is genuinely enough, including for real use.

```bash
pip install -r requirements.txt
python run.py --demo     # try it with a fake sample plant, OR:
python run.py            # real use: reads whatever's in data/corpus/
```
No Docker, no database, no `make`, no API key required for either. Opens at
**http://localhost:8000/ui**. Ctrl+C stops it.

- **`--demo`** generates a fake synthetic sample plant so you can see every
  feature immediately. Use this to try the product. Never use it for real data.
- **No flag** generates nothing fake — it reads whatever real documents you've
  put in `data/corpus/<folder>/` (see below) and serves the app the same way.
  If `data/corpus/` is empty, it tells you so and stops instead of faking data.

**Adding your real documents:** drop files under `data/corpus/<folder>/` —
`work_orders/`, `inspections/`, `incidents/`, `permits/`, `regulations/`,
`manuals/`, `procedures/`, `operating_instructions/`, `emails/`, `drawings/`,
`project_files/`, `quality_records/`. Supported formats: `.csv .tsv .txt .md
.eml .pdf .docx .xlsx .pptx` and images (P&IDs). Then just re-run
`python run.py` — merging is idempotent, so re-running after adding more
files never duplicates anything.

```bash
make test         # regression tests
make scorecard    # every judged metric, computed live
```

## Want smarter, cloud-polished answers? Add a free Gemini key

The system already gives correct, cited answers with **no key at all** —
composed locally from the same evidence. A key only makes the final answer
read as a polished paragraph instead of a plainer, code-composed one.

```bash
cp .env.example .env
```
Then open `.env` and paste your key on this line:
```
GEMINI_API_KEY=your-key-here
```
Get a free key at **https://aistudio.google.com/apikey** (no credit card).
Restart and you're done. This is the **online** path. Prefer to run the model
fully offline on your own machine instead? See "Going fully offline" below.

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

---

## Optional: everything in Docker (app + local LLM + persisted graph)

Everything above already builds the knowledge graph and serves the API — no
database required, no Docker required. Docker is an add-on for two separate
things, and you can use either, both, or neither:
- **Persisted graph** — Neo4j, so the graph survives a restart without
  re-ingesting, and is browsable/queryable with Cypher.
- **A fully local LLM** — an Ollama container serving the two models from
  "Going fully offline" above, so the narrative/vision layer never leaves
  your machine.

**Install Docker first, if you don't have it:**
- **Linux:** `curl -fsSL https://get.docker.com | sh` (official convenience
  script; installs Docker Engine + the Compose plugin — no separate "Desktop"
  app on Linux), then add yourself to the docker group so you don't need
  `sudo` every time: `sudo usermod -aG docker $USER` (log out/in after).
- **Mac / Windows:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (free).

**Then, one command:**
```bash
make docker-up
```
This builds the app image and starts it alongside Ollama and Neo4j — UI at
http://localhost:8000/ui, Neo4j's browser at http://localhost:7474. The app
container reads whatever's in `data/corpus/`
on startup the same way `python run.py` does (no fake data, ever); add more
documents live via "Connect knowledge" or by dropping files into
`data/corpus/` and running `docker compose restart app`.

**No Ollama model is downloaded automatically** — that's a deliberate,
separate step, since the models are several GB:
```bash
make ollama-pull                     # pulls both models into the container
# then in .env: LLM_PROVIDER=ollama
docker compose restart app
```

The Docker image is intentionally lightweight — no Docling, no `torch` (see
`requirements-docker.txt`). If you need to read real PDF/Word files, do that
ingestion once locally with `python run.py --full`, rather than installing
those heavy packages into the always-on container.

`make down` / `make docker-down` stops everything. Everything else — `/ask`,
compliance, RCA, warnings, the UI — works identically with or without any of
this; the API never requires Neo4j or Ollama to be running.

---

## Want to go deeper?

If you want to run one pipeline stage at a time, see every `make` target
explained, or just see the project layout — that's all in the
**[Admin & Developer Guide](docs/ADMIN_GUIDE.md)**.
See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the architecture diagram.
