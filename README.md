# Unified Asset & Operations Brain
ET AI Hackathon 2026 · Problem Statement #8 — Industrial Knowledge Intelligence

See **[PLAN.md](PLAN.md)** for the full plan and **[CLAUDE.md](CLAUDE.md)** for the
engineering guide. Everything runs locally and free.

**Documentation:** [User Guide](docs/USER_GUIDE.md) — for plant staff, how to use
every tab · [Admin & Developer Guide](docs/ADMIN_GUIDE.md) — configuration, data
onboarding, endpoints, the full internal pipeline, troubleshooting.

## ⚡ Setup — one command, nothing else needed
```bash
python run.py
```
That's it. No Docker, no database, no API key, nothing to download. It installs
the handful of small Python packages it needs, generates a sample plant's
worth of documents, reads them, and opens the app at
**http://localhost:8000/ui**. Ctrl+C stops it.

```bash
make test         # regression tests
make scorecard    # every judged metric, computed live
```

## Want smarter, cloud-polished answers? Add a free Gemini key

`python run.py` already gives correct, cited answers with **no key at all** —
composed locally from the same evidence. A key only makes the final answer
read as a polished paragraph instead of a plainer, code-composed one. To add
one:

```bash
cp .env.example .env
```
Then open `.env` and paste your key on this line:
```
GEMINI_API_KEY=your-key-here
```
Get a free key at **https://aistudio.google.com/apikey** (no credit card).
Restart `python run.py` and you're done — nothing else to configure. This is
the **online** path (Gemini's cloud API). If you'd rather run the language
model fully offline on your own machine instead, see
["Going fully offline"](#going-fully-offline--local-models-via-ollama-optional-not-downloaded-for-you) below.

## Common questions about setup

**Do I need Docker?** No. Docker only exists for people who *choose* to persist
the knowledge graph in a real database (Neo4j) instead of rebuilding it from
files each run — that's an optional, advanced path (see the admin guide's
appendix). The app you actually use never touches it.

**Why does the repo have so many `make` commands?** Because each internal
pipeline stage (ingest, graph-build, ask, compliance, RCA, warnings, scorecard)
can be run and tested on its own — useful for development, irrelevant for
using the product. Day to day you only need `python run.py`, `make test`, and
`make scorecard`.

**What does `--full` do?** `python run.py --full` installs Docling (reads real
PDFs) and turns on AI-based fact extraction during ingestion. Skip it unless
you're feeding in real PDF documents — the default already reads CSVs and
plain text and extracts tags/dates with plain code, no AI needed.

**What are "Level 0/1/2/3…"?** Internal engineering shorthand for pipeline
stages, left over from how this was built in order. It doesn't mean anything
is missing if you never see those names — `python run.py` already runs all of
it.

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

With no API key at all, `python run.py` still gives cited, confidence-scored
answers — the cloud model only adds a polished paragraph on top. See the
in-app **"Help"** tab for the live version of this table, and
[CLAUDE.md](CLAUDE.md) for why this matters for plants that legally can't send
data to a foreign cloud.

### Going fully offline — local models via Ollama (optional, not downloaded for you)

Everything above already runs with **zero LLM at all**. If you also want the
polished narrative and drawing-reading to run on your own machine instead of
the cloud, install [Ollama](https://ollama.com/download) and pull two models —
balanced, mid-size (7B) so they run on a normal laptop CPU/GPU without needing
a data-center card, and strong for this specific job (structured extraction /
reading text off an image) rather than the biggest model available:

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

**Want to stress-test with a large plant?** The sample size scales:
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

Everything above is genuinely all you need to run and use the product. If you
want to run one pipeline stage at a time, persist the graph in Neo4j, add real
(non-synthetic) documents, or just see the project layout — that's all in the
**[Admin & Developer Guide](docs/ADMIN_GUIDE.md)**, clearly marked optional.
See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the architecture diagram.
