# Unified Asset & Operations Brain
ET AI Hackathon 2026 · Problem Statement #8 — Industrial Knowledge Intelligence

See **[PLAN.md](PLAN.md)** for the full plan and **[CLAUDE.md](CLAUDE.md)** for the
engineering guide. Everything runs locally and free.

**Documentation:** [User Guide](docs/USER_GUIDE.md) — for plant staff, how to use
every tab · [Admin & Developer Guide](docs/ADMIN_GUIDE.md) — configuration, the
local (no-Docker) setup, per-stage commands, endpoints, troubleshooting.

## Setup — Docker, one command

**Install Docker first, if you don't have it:**
- **Linux:** `curl -fsSL https://get.docker.com | sh` (official convenience
  script; installs Docker Engine + the Compose plugin — no separate "Desktop"
  app on Linux), then add yourself to the docker group so you don't need
  `sudo` every time: `sudo usermod -aG docker $USER` (log out/in after).
- **Mac / Windows:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (free).

Then pick exactly one command. Each one **builds the image and starts it** —
there's no separate build step, no other command to run first:

| # | Command | Does |
|---|---|---|
| **1** | `make docker-app` | Simple app, nothing else. Uses Gemini if `GEMINI_API_KEY` is in `.env` (see below) — otherwise still answers correctly, just without the polished narrative. |
| **2** | `make docker-ollama` | Simple app + Ollama. **Pulls both local-LLM models automatically** (~11GB, the one real download) and switches the app to use them. |
| **3** | `make docker-neo4j` | Simple app + Neo4j — persisted graph, Cypher browser at http://localhost:7474. |
| **4** | `make docker-both` | Simple app + Ollama + Neo4j together. |

`make docker-down` stops whichever one you started. Opens at
**http://localhost:8000/ui** once it's up.

**The only manual step anywhere is the Gemini key** (skip it entirely if
you're using `make docker-ollama`/`make docker-both`):
```bash
cp .env.example .env
```
then open `.env` and paste your key on the `GEMINI_API_KEY=` line — get a
free one at https://aistudio.google.com/apikey.

## Want to try it with sample data first?

```bash
make docker-demo          # generate + ingest a fake sample plant
make docker-demo-undo     # remove exactly what that added
```
(Or the same two actions as buttons in the UI's "Connect knowledge" tab.)
**Safe to run even against a real deployment** — every fake file lives under
a `data/corpus/<category>/demo/` subfolder, so it can never overwrite a real
file of the same name, and the undo command removes exactly (and only) what
was added. (One exception: sensor readings live in one flat file, not a
folder — the generator refuses to touch it if it already has real data, see
[ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md).) Verified: added demo data, confirmed
a "real" file at the same canonical filename survived untouched, then fully
reverted with the undo command back to the exact original state.

## Adding your documents — through the UI, that's the only way

Once it's running, open the **"Connect knowledge"** tab and drag in your
files — **you can drop or select several files at once**, they're ingested
immediately, and the very next question can use them. No file-system
folders to manage, no restart, no separate ingestion command.

- **Always supported, no addon:** `.csv .tsv .txt .md .eml .pdf .docx .xlsx .pptx`
  — normal digital files with real text (not a scan) read directly with plain
  code (`pypdf`/`python-docx`/`python-pptx`/`openpyxl`), no AI, no heavy install.
- **Scanned PDF pages** (a photo of a page, no text layer) are read by the
  **same vision model already configured** for drawings (Gemini, or
  `make docker-ollama`'s local model) — no extra install needed if you're
  already using one of those.
- **Only if no vision model is configured at all**, scanned pages and legacy
  `.doc`/`.xls`/`.html` fall back to the heavier Docling addon — build with
  `INSTALL_PDF=true docker compose build app` (Docker) or `python run.py --full`
  (local). See [ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md) for detail.
- **Drawings/P&IDs (images)** need a vision model — automatic with
  `make docker-ollama`/`make docker-both`, or Gemini if you added a key above.

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
in-app **"Help"** tab for the live version of this table.

`make docker-ollama` (above) already installs and runs the local-LLM path —
two balanced, mid-size (7B) models chosen deliberately over bigger ones
(don't need a data-center GPU) and smaller ones (miss fields in structured
extraction): **Qwen 2.5 7B Instruct** for text, **Qwen 2.5-VL 7B** for reading
tags off drawings (validated end-to-end on a synthetic P&ID — 7/7 tags read
correctly, see `eval/vision_probe.py`). This swap hasn't been run live in
this project yet beyond that test; Gemini has been the one exercised fully
end to end so far.

---

## Want to go deeper?

Running it without Docker, per-stage `make` targets, the project layout, and
full configuration reference — that's all in the
**[Admin & Developer Guide](docs/ADMIN_GUIDE.md)**.
See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the architecture diagram.
