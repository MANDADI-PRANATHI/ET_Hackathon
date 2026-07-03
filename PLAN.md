# Build Plan — Sutradhar: The Unified Asset & Operations Brain

### ET AI Hackathon 2026 · Problem Statement #8: AI for Industrial Knowledge Intelligence

**Submission date: 22 July 2026 · Solo build, ~19 days runway**

---

## 0. Naming the thing

We call the product **Sutradhar** — the "thread-holder," the figure in Indian classical
theatre who stands at the edge of the stage, holds every character's thread, and narrates
how they connect. That is exactly the job description in the problem statement: hold every
document's thread — a drawing, a work order, a regulation, an incident report — and narrate
how they connect to one asset, one decision, one answer. It is a name a judging panel from
an Indian heavy-industry background will immediately understand, and it doubles as the
one-line pitch: *"Sutradhar is the thread-holder for your plant's knowledge."*

---

## 1. What we're building (in one paragraph)

A large plant's knowledge lives across 7–12 disconnected systems — P&IDs in one place,
work orders in another, safety procedures in a third, inspection records in a fourth,
regulatory paperwork buried in email. Engineers lose roughly a third of their working
hours hunting for information that already exists somewhere. Maintenance decisions get
made without full equipment history, contributing to 18–22% of unplanned downtime in
Indian heavy industry. And a quarter of India's most experienced engineers retire within
the decade, taking undocumented judgment calls — the "why," not just the "what" — with
them. **Sutradhar is a single knowledge brain that reads every document type the plant
produces, builds a living, asset-centred knowledge graph out of them, and lets anyone —
technician, engineer, safety officer, auditor, on a phone or a desktop — ask a plain-English
question and get a trustworthy answer with the exact source and a calculated confidence
level.** On top of that, it runs three agents that *do work*, not just answer questions: it
checks the plant against regulation, investigates why equipment failed, and pushes
warnings before a known failure pattern repeats — and it keeps itself current automatically
as new documents land, so the brain never goes stale the way a wiki does.

---

## 2. How the whole thing works

A four-stage pipeline, each stage independently demoable:

1. **Read everything.** Every document type named in the brief — P&IDs/drawings, work
   orders, safety procedures, inspection reports, operating instructions, project files,
   spreadsheets, scanned forms, email archives — goes through a router that sends it to the
   right extractor and comes out the other side as clean, source-stamped facts.
2. **Connect the dots.** Facts become nodes and edges in a knowledge graph built **around
   the asset**: every pump, valve, and vessel is a hub with its documents, work orders,
   inspections, incidents, live readings, manuals, and people all linked to it —
   *Pump P-101 → maintained by → Work Order 4471 → references → Manual page 12 →
   governed by → OISD-105*. The graph updates itself through a real ingest-merge-refresh
   pipeline every time a new document arrives — not a one-time load.
3. **Answer questions.** Anyone asks in plain English and gets a clear answer, the exact
   sources (clickable, down to the page), and a calculated confidence score — framed for
   their role.
4. **Take action.** Three always-on agents use the same brain to check compliance and
   flag quality issues, investigate failures using documents *and* live operating
   conditions, and proactively push warnings before a known bad pattern recurs.

```
Messy documents ─▶ Read & extract facts ─▶ Auto-updating knowledge graph
  (Level 1)              (source + confidence           (Level 2)
                           on every fact)                    │
                ┌──────────────────────────┬──────────────────┴──────────────┐
                ▼                          ▼                                  ▼
      Ask-Anything Copilot      Compliance + QMS Agent            Maintenance/RCA Agent
        (Level 3 — GraphRAG,     (Level 4a — hybrid rule           + Lessons-Learned Agent
         citations, confidence,   engine, evidence packs,          (Level 4b/4c — live
         role-aware, mobile,      non-conformances, CAPA)           conditions, predictive
         voice input)                                               maintenance, proactive
                                                                      warning feed)
                                        │
                                        ▼
                        Live Scorecard Dashboard (Level 5)
              — every judged metric computed and shown, in-product
```

---

## 3. How we cover every part of the brief — completely

**The five buildable components — all covered, and each pushed a step further than the
literal ask:**

| Component in the brief | Where in our plan | How we go beyond the minimum |
|---|---|---|
| 1. Universal Document Ingestion & Knowledge Graph | Levels 1 & 2 | Auto-updating pipeline demoed live (drop a file mid-demo, watch the graph and answers change); deterministic + AI hybrid extraction for auditable accuracy |
| 2. Expert Knowledge Copilot | Level 3 | GraphRAG (graph traversal + meaning search combined), not simple RAG; mobile-first, voice input for field technicians with dirty hands; deliberately tests cross-functional discovery |
| 3. Maintenance Intelligence & RCA | Level 4b | Fuses static docs with a live "readings adapter" (OPC-UA/MQTT-shaped) so RCA reasons over *current* plant state, not just history |
| 4. Quality & Regulatory Compliance | Level 4a | Hybrid rule engine: AI reads the regulation, code makes the yes/no call — auditors can trust the verdict, not just the explanation; auto-generates a PDF evidence package |
| 5. Lessons-Learned & Failure Intelligence | Level 4c | Internal pattern mining + external CSB/OISD incident correlation; **pushes** warnings via an alert feed instead of waiting to be asked — directly answers the "before similar conditions recur" language in the brief |

**The six suggested technologies — all covered:**

| Suggested technology | Where |
|---|---|
| RAG over heterogeneous documents | Level 3 |
| Knowledge Graphs & Industrial Ontology Engineering | Levels 0 & 2 — a standards-based (ISA-95 / ISO 14224 / IEC 81346), swappable vocabulary |
| Computer Vision (P&ID parsing, drawing digitisation) | Level 1 — vision-model drawing reader with a human-confirm step |
| OCR & Document Intelligence | Level 1 — layout-aware document reader for scans, tables, forms |
| QMS Integration | Level 4a — non-conformances, CAPA workflows, plug-in slot for a real QMS |
| Agentic AI for maintenance and compliance | Level 4 — three purpose-built agents with visible reasoning traces |

**The four required deliverables — all covered (Level 5):** Working Prototype ·
Architecture Diagram · Presentation Deck · Demo Video.

**The evaluation focus — each metric has an owner, a measurement, and a live dashboard
tile so judges see the number, not just a claim:**

| Judged on | Where we earn it | How it's shown |
|---|---|---|
| Entity extraction accuracy across document types | Level 1, hand-labelled benchmark set | Scorecard tile, per document type |
| Query answer quality on expert benchmark questions | Level 3, curated Q&A benchmark scored with an automated answer-quality rubric | Scorecard tile with pass/fail breakdown |
| Knowledge-graph linkage completeness | Level 2 | Scorecard tile + live graph visualisation |
| Time-to-answer vs. traditional search | Level 3, measured against a real keyword-search baseline built alongside it | Side-by-side timer in the demo |
| Compliance-gap detection accuracy | Level 4a, measured against known planted gaps + labelled regulation clauses | Scorecard tile |
| Cross-functional knowledge discovery | Level 3, measured as % of benchmark answers whose best evidence comes from a different department than the question's origin | Scorecard tile — our signature differentiator |
| Validated on real industrial samples | Real public documents (CSB investigation reports, OISD standards, OSHA PSM, OEM manuals) used throughout | Named and cited in the deck |

---

## 4. Mapping straight to the judging weights

We designed features against the scorecard, not just the feature list, so nothing we build
is judged-criteria-neutral:

| Criterion | Weight | What earns it |
|---|---|---|
| **Innovation** | 25% | GraphRAG combining graph traversal + meaning search (not "PDF search with a chatbot"); hybrid deterministic/AI extraction with per-fact confidence provenance; hybrid AI-parses/code-decides compliance engine; proactive warning agent that pushes instead of waiting; in-product live scorecard that self-grades against the brief's own evaluation criteria in real time |
| **Business Impact** | 25% | Every number in the pitch traces to the brief's own cited stats (35% time lost, 18–22% downtime, 25% retiring workforce); compliance evidence packages map to real Indian statutes (Factory Act, OISD, PESO); fully offline-capable deployment story matters concretely to regulated Indian plants that legally cannot send drawings/incident data to a foreign cloud |
| **Technical Excellence** | 20% | Standards-grounded ontology (ISA-95/ISO 14224/IEC 81346); asset-centric graph with real entity-resolution (alias lists + similarity + human-confirm, deliberately *not* over-merging near-duplicate equipment); every fact traceable to its exact source sentence; automated eval harness (extraction accuracy, answer quality, linkage completeness) built incrementally, not bolted on at the end |
| **Scalability** | 15% | Swappable industry ontology proven live in the demo (flip from oil & gas to manufacturing on one config change); adapter pattern for live sensor feeds (OPC-UA/MQTT-shaped) so production deployment is a plug, not a rewrite; ingestion pipeline designed for incremental updates at any volume, not a one-shot batch job |
| **User Experience** | 15% | Mobile-first, works one-handed in the field; voice input for technicians who can't type with gloves on; role-aware answers (technician vs. engineer vs. safety officer vs. auditor see different framing of the same fact); every claim is a clickable citation, so trust is inspectable, not asserted |

---

## 5. Generic engine, oil & gas as the showcase

The engine is **industry-agnostic** — it works for any asset-heavy plant (manufacturing,
power, oil & gas). The only industry-specific piece is the ontology YAML — a swappable
vocabulary profile. We build the oil & gas profile first because that is where the richest
*real, public* documents exist (CSB investigation reports, OISD standards) and where the
compliance story is strongest, but the demo includes a **live ontology swap** — flipping to
a manufacturing profile on stage — to prove Scalability isn't just a slide claim.

---

## 6. What it costs

**Nothing.** All storage and compute run on local infrastructure (Docker) or a free-tier
cloud model. The "thinking" layer sits behind one setting (`LLM_PROVIDER=gemini|ollama`),
so the whole system can run **fully offline** on a laptop with zero internet dependency —
a genuine requirement for regulated Indian plants (OISD/PESO sites) that are not legally
permitted to send drawings or incident data to a foreign cloud. That's not a cost-saving
trick, it's a real deployment advantage worth stating plainly in the business-impact
narrative.

---

## 7. The tools, trimmed to what actually earns its place

We deliberately kept the stack smaller than originally planned — every framework
evaluated during the build and cut in favour of plain, explainable code is listed
below alongside what shipped, because the cuts are as much a design decision as
the inclusions:

| Tool | What it does | Why it's in (not just "why not") |
|---|---|---|
| **Docling** | Reads PDFs, Word, spreadsheets, scanned pages into clean text/tables | Saves weeks of layout-parsing code |
| **Vision-capable LLM (cloud or local via Ollama)** | Reads P&IDs and scanned drawings directly as images, extracting tags/lines/instrument numbers | Avoids building a bespoke CV pipeline (symbol/line detection) that would eat most of the runway for marginal gain — a pragmatic way to satisfy the "computer vision" ask, and Ollama's Qwen-VL/GLM-OCR make it fully offline-capable too |
| **Local embeddings + reranker (BGE, via `sentence-transformers`)** | Local hybrid passage search: BM25 keyword + dense cosine, fused by Reciprocal Rank Fusion, then cross-encoder reranked | Free, on-device, zero API latency or cost — and this is the retrieval engine judges see in the demo, not a placeholder for one |
| **Neo4j** | Stores facts as nodes/edges, asset-centric; can also host a vector index | Optional for the demo — the copilot and every agent run identically on an in-memory `GraphModel`, so the whole product works with zero database running |
| **FastAPI** | Backend server + the single-file mobile UI's API surface | Standard, fast, typed, no framework lock-in |
| **A time-series table + readings adapter** | Holds recent equipment readings (temperature, vibration, pressure); a replayed data file feeds it for the demo, real OPC-UA/MQTT plugs into the same slot | Makes "real-time operating conditions" concrete without needing a real plant feed |
| **A plain-code compliance rule checker** | Executes the parsed rule against actual dates/records/readings and returns a hard met/gap/unknown | The pass/fail decision is never left to a model's guess — this is the credibility anchor for the compliance agent |
| **A local, embedding-based faithfulness scorer** | Checks whether an answer's claims are grounded in the cited evidence | Gives the scorecard a real "answer quality" number with **zero LLM-judge calls** — the evaluation doesn't depend on the same API the product doesn't depend on |

**Cut from the original plan, on purpose, once the trade-off was concrete:**
- **LlamaIndex** — retrieval stayed as our own ~150 lines of hybrid-search code
  (`retrieval/knowledge.py`). Fewer abstraction layers means the demo can show
  *exactly* how an answer was assembled, and it's the difference between
  depending on a framework's embedding/reranker wiring and owning it outright.
- **A generic agent-orchestration framework** (e.g. LangGraph) — the three
  Level 4 agents (`agents/compliance.py`, `agents/rca.py`, `agents/lessons.py`)
  are each a short, readable Python function. None of them needed multi-step
  planning or tool-calling loops; adding a framework would have been
  complexity with no corresponding capability.
- **RAGAS** — its faithfulness score is LLM-judge-based, which would have made
  *evaluating* the product depend on the same cloud call the product is
  designed to minimise. Replaced with the local embedding-based scorer above.
- **Next.js** — the UI is one dependency-free HTML/CSS/JS file
  (`web/index.html`) served as a static mount by FastAPI. Lower demo risk (no
  build step, nothing to fail to compile) and it's still mobile-first with
  voice input; a Next.js rewrite remains a drop-in upgrade if ever needed at
  a larger scale.

### Local-first retrieval, Neo4j optional

The original plan's "two stores" (a vector index and a graph database) are both
real in production, but the demo doesn't require either running:

- **Meaning search** — BM25 + local embeddings + local reranker, entirely
  in-process. Neo4j's vector index is available for scale but not on the
  critical path.
- **Connections** — the in-memory `GraphModel` (`graph/model.py`) is what the
  copilot and every Level 4 agent actually query. `stores/graph_writer.py`
  persists the same model into Neo4j when it's reachable, for querying the
  graph directly (Cypher) at larger scale — but nothing in the demo path
  requires the database to be up.

The copilot uses graph traversal and hybrid search together — search finds
candidate passages, the graph supplies the relationships that make an answer
*explainable*, not just plausible — and it does so identically whether or not
Neo4j, or even a cloud LLM, is reachable.

---

## 8. How the fact-finding actually works (deliberately not "all AI")

| Kind of information | How we get the facts | AI involved? |
|---|---|---|
| Spreadsheets, work-order tables, quality records | Read columns directly with plain code | No |
| Predictable codes (P-101, dates, OISD-105) | Regex pattern rules | No |
| Layout & tables in PDFs | Layout-aware document reader organises, doesn't invent | Not the guessing kind |
| Facts buried in prose (reports, procedures, emails) | Model reads the prose, extracts facts + links, output constrained to a fixed schema | Yes, fenced in |
| Drawings and scans | Vision model reads the image, tags stamped as low-confidence until human-confirmed | Yes, with a checkpoint |
| "P-101" = "Pump 101"? | Mostly similarity math; model judges only the genuinely unclear cases | Mostly no |

Wherever a model is used: it must use the fixed ontology vocabulary, its output must
validate against a strict schema, **every fact is tied to its exact source sentence**
(this is what powers the citations and the confidence score), low-confidence extractions
are flagged rather than silently trusted, and facts confirmed across multiple documents
score higher. This is the credibility foundation the whole product stands on.

---

## 9. The build, layer by layer

Six levels, each independently demoable, each adding to the last.

### Level 0 — Foundation *(done)*

Local infrastructure (Neo4j, Postgres, MinIO), the standards-grounded oil & gas ontology
profile, LLM provider switch, schema init, synthetic plant records (with a deliberately
overdue PSV-110B inspection planted for the Level 4a demo), health-check script.

### Level 1 — Read everything & extract facts

- Router sends each document to the right extractor: normal files → document reader;
  drawings and scans → vision-model reader with a human-confirm checkpoint.
- Structured files (spreadsheets, tables, quality records) read directly by code — no
  model in the loop where it isn't needed.
- **Every extracted fact is stamped with its exact source passage and an extraction
  confidence** — this travels with the fact all the way to the final answer.
- Documents split into meaning-tagged, searchable passages.
- **Build the entity-extraction benchmark set here** (hand-label a sample from each
  document type) so accuracy is measured from day one, not estimated later.
- **Build the keyword-search baseline here too** — a simple full-text index — so the
  "time-to-answer vs. traditional search" comparison has a real opponent, not a strawman.

**Done when:** a mixed folder produces clean, source-stamped facts and searchable
passages, and extraction accuracy is measured against the benchmark.

### Level 2 — Build the web of connections

- Every fact becomes a node, every relationship an edge, the **asset is the hub**.
- Entity resolution done properly: normalise tags by pattern, maintain an alias list, use
  similarity to propose matches, let the model judge only the genuinely unclear cases with
  a human-confirm step. Deliberately avoid over-merging — "P-101A" and "P-101B" are
  usually distinct backup pumps, not one asset, and every alias records where it came from.
- **Real update pipeline:** new document → extract → compare against existing graph →
  merge/resolve duplicates → update the graph → refresh affected embeddings → invalidate
  stale cached answers. Demoed live by dropping a new file mid-presentation and watching
  the graph and a follow-up answer change.

**Done when:** the graph is visualisable, linkage completeness and merge accuracy are
measured, and a live re-ingest correctly updates the graph and the copilot's answers.

### Level 3 — The Ask-Anything Copilot *(centerpiece)*

- Real GraphRAG, not "search then ask": spot the topic → jump to its hub in the graph and
  pull its neighbours → also pull meaning-matched passages → combine both → write the
  answer. The graph is what makes cross-functional answers possible.
- Every claim is a clickable citation to the exact document and page.
- **Confidence is computed, not asserted** — built from extraction confidence, linkage
  strength, retrieval match quality, and multi-document agreement. Weak evidence is stated
  as weak, not smoothed over.
- Role-aware framing: technician, engineer, safety officer, and auditor get the same fact
  framed for their job; sensitive personal data is access-controlled by role.
- **Mobile-first UI with voice input** — a field technician with gloves and dirty hands can
  ask a question by speaking into a phone and get a streamed, cited answer back.
- The benchmark deliberately includes cross-functional questions (best answer sourced from
  a different department than where the question started) to measure that specific metric.

**Done when:** it answers benchmark questions correctly with real citations, beats the
keyword-search baseline on time-to-answer, and the cross-functional discovery rate is
measured and shown on the scorecard. *This alone is a complete, demoable product.*

### Level 4 — The agents that set us apart

**4a. Compliance & Quality (QMS) agent — built first, highest confidence, highest value**

- Hybrid by design: a model turns each regulation clause into a precise, checkable rule
  ("valves of this class → inspection every 6 months"); a **plain-code checker** then runs
  that rule against the actual graph data (last inspection date vs. limit, equipment
  state, exceptions) and returns a hard **met / gap / unknown** — the yes/no decision is
  never left to a model's guess.
- Produces an **auto-generated, audit-ready PDF evidence package**, raises
  non-conformance records, and drafts CAPA (corrective-action) workflows, each tied to its
  evidence. A plug-in slot allows connecting to a real QMS later via standard files/APIs.

**Done when:** it produces a real evidence package against real regulation text and
gap-detection accuracy is measured against known planted gaps.

**4b. Maintenance & RCA agent**

- Pulls work-order history, failure records, OEM manuals, and inspection findings from the
  graph, plus **live operating readings** (temperature, vibration, pressure) through a
  readings adapter — fed by a replayed data file for the demo, with the same adapter
  ready to accept a live OPC-UA/MQTT feed in production.
- Produces a root-cause analysis with cited evidence, predictive maintenance
  recommendations, and an optimised maintenance schedule.

**Done when:** RCA output matches known causes in the benchmark scenarios and a sample
optimised schedule is generated.

**4c. Lessons-Learned & proactive warning agent**

- Mines the plant's own incident, near-miss, audit, and non-conformance history for
  recurring patterns invisible to any single review.
- Folds in external public incident reports (e.g. CSB investigations) only where they map
  cleanly onto the ontology, so external noise never pollutes internal accuracy.
- **Proactively pushes warnings** to the relevant team through an alert feed — before a
  known bad pattern recurs, not on request. This directly answers the "before similar
  conditions recur" language in the brief.

**Done when:** a real recurring pattern is surfaced from the corpus and a matching warning
is pushed automatically.

### Level 5 — Prove it, scale it, present it

- **Live in-product scorecard**: every judged metric (extraction accuracy, answer
  quality, linkage completeness, time-to-answer, compliance-gap accuracy,
  cross-functional discovery) computed and displayed inside the product itself — judges
  see the number generated live, not just quoted in a deck.
- **Scalability demo**: swap the ontology profile live (oil & gas → manufacturing) and
  re-run a query to prove the engine is generic.
- Role-based access control finished as polish once the scored features are solid.
- Architecture diagram, presentation deck, and demo video produced from real numbers and
  a real running system.

**Done when:** one command regenerates the scorecard, the demo video is recorded end to
end without a script cut, and the deck is ready.

> **Must-have line:** Levels 0–3 are a complete, demo-ready product on their own.
> Level 4a is the next priority after that (fastest to make bulletproof — the compliance
> gap is planted in the data). 4b and 4c follow if the runway allows, which at 19 days it
> comfortably should.

---

## 10. Nineteen-day schedule (3 Jul → 22 Jul 2026)

| Days | Dates | Focus |
|---|---|---|
| 1 | Jul 3 | De-risk spike: run the vision model against a real P&ID and confirm tag extraction quality; scaffold the eval harness |
| 2–3 | Jul 4–5 | Level 1: document router, structured readers, vision-drawing reader + human-confirm, source+confidence stamping, entity-extraction benchmark set, keyword-search baseline |
| 4–6 | Jul 6–8 | Level 2: asset-centric graph build, entity resolution, live re-ingest pipeline, graph visualisation |
| 7–9 | Jul 9–11 | Level 3: GraphRAG copilot, citations, computed confidence, role-aware framing, mobile UI + voice input, cross-functional benchmark questions |
| 10 | Jul 12 | Level 4a: compliance rule engine, evidence-package generator, non-conformance/CAPA workflow |
| 11 | Jul 13 | Level 4b: RCA agent, readings adapter, replayed live-conditions feed |
| 12 | Jul 14 | Level 4c: lessons-learned mining, proactive warning feed |
| 13–15 | Jul 15–17 | Level 5: live scorecard dashboard, ontology-swap scalability demo, RBAC polish, architecture diagram |
| 16–17 | Jul 18–19 | Presentation deck + demo video production |
| 18–19 | Jul 20–21 | Buffer: bug fixes, full dry-run rehearsal |
| — | Jul 22 | Submission |

---

## 11. How we prove it works

Judges score on named, specific measurements — so we compute exactly those, live, inside
the product, from day one: extraction accuracy, answer quality, linkage completeness,
time-to-answer vs. keyword search, compliance-gap detection accuracy, and cross-functional
knowledge discovery — all validated against real public industrial documents (CSB
investigation reports, OISD standards, OSHA PSM, OEM manuals), not synthetic-only data.

---

## 12. Why this wins

- Most entries will demo "chat with your PDFs." We demonstrate **knowledge connecting
  across departments** — the actual point of the problem statement — and we measure it as
  a number, live, on stage.
- Every answer is **traceable and confidence-scored**, and framed differently for the four
  different roles named in the brief — trust is inspectable, not asserted.
- The three agents **do real work**: a compliance verdict a code path can defend, an RCA
  grounded in live conditions, and warnings that arrive before anyone asks.
- The scorecard is **inside the product**, not just the deck — judges watch the evaluation
  criteria get satisfied in real time.
- It runs **fully offline on local hardware**, which is a genuine deployment requirement
  for the regulated Indian plants this problem statement is written for — not a budget
  trick, a business fit. This isn't just the LLM behind a switch: **retrieval itself
  is local hybrid search** (BM25 + on-device embeddings + a local reranker), every agent
  verdict is plain code, and the copilot composes a fully readable, cited answer with
  zero LLM calls if none is configured. A judge can pull the network cable and the
  product keeps working — few "AI platform" entries can make that claim honestly.
- The whole engine swaps industries on one config file, proven live — Scalability is
  demonstrated, not claimed.
- Even the **evaluation** doesn't depend on a cloud API: the answer-faithfulness metric
  is computed by a local embedding model, so every number on the scorecard is
  reproducible with no internet connection at all.

---

## 13. One design rule throughout

The "brain" sits behind a simple switch — swap the model provider, the industry
vocabulary, or the QMS connection without rewriting anything else. Every new capability
gets added at the layer that already owns that kind of decision (code for deterministic
facts, the model for prose, the graph for connections) rather than reaching for the model
to do something a few lines of code can do more reliably. And the switch always defaults
toward the option that needs less: local before cloud, code before a model call, cached
before recomputed — an API is something the product can use to get better, never something
it requires to be correct.
