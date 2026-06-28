# Build Plan — Unified Asset & Operations Brain

### ET AI Hackathon 2026 · Problem Statement #8: AI for Industrial Knowledge Intelligence

---

## 1. What we're building (in one paragraph)

A big plant keeps its knowledge scattered across 7–12 disconnected systems — engineering drawings in one place, maintenance work orders in another, safety procedures in a third, inspection records in a fourth, regulatory papers buried in email. Engineers waste about a third of their time hunting for information, decisions get made without full equipment history (causing ~18–22% of unplanned downtime), and when experienced people retire, decades of know-how disappear. We're building a single **"brain"** that reads **all** of those documents, understands how everything connects, and lets **anyone — in any role, on any device** — ask a plain-English question and get a trustworthy answer **with the exact source and a confidence level**. On top of that, it actively **does work**: checks the plant against safety/quality regulations, investigates *why* equipment failed, and pushes early warnings before problems repeat. It keeps itself **up to date automatically** as new documents arrive.

---

## 2. How the whole thing works (the simple version)

A four-step assembly line:

1. **Read everything.** Feed in all the messy documents — drawings/P&IDs, work orders, safety procedures, inspection reports, operating instructions, project files, spreadsheets, scanned forms, and email archives. The system reads each one and pulls out the important facts.
2. **Connect the dots.** Those facts go into a "web of connections" (a knowledge graph) built **around the asset** — every pump, valve, and vessel is a *hub*, with its documents, work orders, inspections, incidents, sensor readings, manuals, and the people involved all linked to it. So nothing sits alone: *Pump P-101* → *maintained by* → *Work Order 4471* → *references* → *Manual page 12* → *governed by* → *Safety Rule OISD-105*. The web updates as new documents arrive (a real step-by-step pipeline — see Level 2, not magic).
3. **Answer questions.** Anyone asks a question and gets a clear answer, the **exact sources**, and a **confidence level** — tailored to their role (a technician, an engineer, a safety officer, an auditor each get what's relevant to them).
4. **Take action.** Assistants use the same brain to *do things*: check compliance and raise quality issues, investigate failures (using both documents **and** live operating conditions), and push warnings before known problems recur.
5. 

```
Messy documents ─▶ Read & extract facts ─▶ Web of connections (auto-updating)
                                                     │
                ┌────────────────────────────────────┼────────────────────────────────────┐
                ▼                                      ▼                                     ▼
        Ask-anything Copilot              Compliance + Quality (QMS)            Maintenance/RCA  +  Lessons-Learned
        (sources, confidence,             (gaps, evidence packs,               (live conditions, predictive,
         role-aware, mobile)               non-conformances, corrective         optimised schedules)  + proactive
                                           actions)                              warnings from past incidents
```

---

## 3. How we cover **every part** of the brief

This is the checklist that proves nothing is missing.

**The five things we may build — all covered:**

| Component in the brief                            | Where in our plan                                                                                                                                                                              |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Universal Document Ingestion & Knowledge Graph | Levels 1 & 2 — reads all formats, extracts entities (equipment tags, process parameters, regulatory references, personnel, dates), auto-updates                                               |
| 2. Expert Knowledge Copilot                       | Level 3 — answers with citations + confidence + links, mobile, role-aware                                                                                                                     |
| 3. Maintenance Intelligence & RCA                 | Level 4b — fuses work orders + failure records + manuals + inspections**+ live operating conditions** → predictive recommendations, root-cause analysis, **optimised schedules** |
| 4. Quality & Regulatory Compliance                | Level 4a — maps Factory Act / OISD / PESO / environmental / quality standards → gaps, evidence packages, flags quality deviations (this is also our**QMS integration**)                |
| 5. Lessons-Learned & Failure Intelligence         | Level 4c — analyses incidents, near-misses, audit findings, non-conformances**+ external industry databases** → patterns → **proactively pushes warnings**                      |

**The six suggested technologies — all covered:**

| Suggested technology                                    | Where                                                                                                 |
| ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| RAG over heterogeneous documents                        | Level 3 (the copilot)                                                                                 |
| Knowledge Graphs & Industrial Ontology                  | Levels 0 & 2 (the web + a standards-based vocabulary)                                                 |
| Computer Vision (P&ID parsing, drawing digitisation)    | Level 1 (reading drawings — its own explicit step)                                                   |
| OCR & Document Intelligence (structured + unstructured) | Level 1 (Docling + reading scanned pages)                                                             |
| **QMS Integration**                               | Level 4a (quality records in, non-conformances + corrective actions out, plug-in slot for a real QMS) |
| Agentic AI for maintenance & compliance                 | Level 4 (the assistants)                                                                              |

**The four required deliverables — all covered (Level 5):** Working Prototype · Architecture Diagram · Presentation Deck · Demo Video.

**The evaluation focus — each has an owner and a measurement (Level 5 scorecard):**

| Judged on                                      | Where we earn it / measure it                                                                                                   |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Entity extraction accuracy                     | Level 1 (measured against hand-labelled docs)                                                                                   |
| Query answer quality on expert questions       | Level 3 (measured on an expert Q&A set)                                                                                         |
| Knowledge-graph linkage completeness           | Level 2 (measured)                                                                                                              |
| Time-to-answer vs traditional search           | Level 3 (measured against keyword search)                                                                                       |
| Compliance-gap detection accuracy              | Level 4a (measured)                                                                                                             |
| **Cross-functional knowledge discovery** | Level 3 — measured: how often the best answer comes from a*different* department's documents than where the question started |
| Validated on real industrial samples           | Real public documents used throughout                                                                                           |

---

## 4. Generic engine, oil & gas as the showcase

We are **not** locked to oil & gas. The **engine is completely general** — it works for any asset-heavy plant (manufacturing, power, oil & gas). The only domain-specific piece is the **"vocabulary" file**, which is a **swappable profile** you load. We use an **oil & gas profile for the demo** because that's where the best *real public documents* exist and where the safety/compliance story is strongest — but we can load a manufacturing or power profile by switching one file, and we'll show that briefly to prove it's general. This also helps the **Scalability** score: it's a platform, not a one-off.

---

## 5. What it costs

**Nothing.** Everything runs free:

- All storage and software runs on your own machine (no cloud bills).
- The "thinking" AI uses **Google Gemini's free tier** *or* a model running **fully offline on your laptop** — either is $0. One setting switches between them.
- The "understanding meaning" part (for search) runs locally and free.

Bonus pitch: because it can run **fully offline on plant hardware**, it suits real industrial customers who legally **can't send drawings and incident data to the cloud** — a genuine business advantage, not just a budget choice.

---

## 6. The tools we use, in plain English

We rely on well-known **free frameworks** — we are *not* hand-writing everything.

| Tool                                               | What it does, plainly                                                                                                                                                                            |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Docling**                                  | Reads PDFs, Word, spreadsheets, and scanned pages and turns messy layouts into clean text and tables.                                                                                            |
| **Gemini (free) or Ollama**                  | The "brain." Gemini is a free online AI; Ollama runs an AI on your own computer. We swap with one setting.                                                                                       |
| **Instructor**                               | Forces the AI to return facts in a tidy, form-like format so the rest of the system can trust and use them.                                                                                      |
| **Neo4j**                                    | The "web of connections." Stores facts as dots and links, lets us ask "show everything connected to P-101," and draws the web as a picture for the demo.                                         |
| **LlamaIndex**                               | The backbone that ties it together: reading documents, building the web, searching, and answering. Saves us tons of plumbing.                                                                    |
| **Local embeddings + reranker (BGE/Nomic)**  | The "understands meaning" part, so "the pump is leaking" matches "seal failure on P-101." Free, on your machine.                                                                                 |
| **LangGraph**                                | Runs the step-by-step assistants (compliance, failure investigation) so they can reason in stages and show their work.                                                                           |
| **RAGAS**                                    | A free testing tool that scores answer quality — gives us real numbers for the judges.                                                                                                          |
| **FastAPI**                                  | The behind-the-scenes server.                                                                                                                                                                    |
| **Next.js**                                  | The app screen — a role-aware chat that works on phones (for field staff) and desktops.                                                                                                         |
| **A "readings adapter" + time-series table** | Holds recent equipment readings (temperature, vibration, pressure). A replayed data file feeds it for the demo; real plant feeds (the standard protocols OPC-UA / MQTT) plug into the same slot. |
| **A plain-code rule checker**                | Makes the exact compliance decisions (is the inspection within the time limit? is the state OK?) so the yes/no answer is never left to the AI's guess.                                           |

### How the data is stored — two layers working together

We deliberately keep **two stores**, each doing what it's best at:

- **The meaning store (a "vector index"):** holds the document passages and their "meaning fingerprints," for fast search by meaning. For the hackathon this lives inside Neo4j's built-in meaning-search to keep it simple. *If* we ever needed to scale to millions of passages, we'd move this part to a dedicated meaning store (Qdrant) — a one-setting change.
- **The connections store (Neo4j):** holds the facts and how they link, built **around the asset** so every pump/valve/vessel is a hub with its history, documents, and readings hanging off it.

The copilot uses **both together**: meaning-search finds the right passages; the connections store reasons across departments. (So we're *not* dumping everything into one tool and hoping — each layer does its own job.)

---

## 7. How the fact-finding actually works (it's not "all AI")

We use the cheapest, most reliable method for each kind of information:

| Kind of information                                     | How we get the facts                                                             | AI?                             |
| ------------------------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------- |
| Spreadsheets, work-order tables, quality records        | Read the columns directly with plain code — the facts are already in the fields | **No**                    |
| Predictable codes (P-101, dates, OISD-105)              | Pattern-matching rules — exact and free                                         | **No**                    |
| Layout & tables in PDFs                                 | A document reader organises them (it doesn't invent)                             | **Not the guessing kind** |
| Facts buried in sentences (reports, procedures, emails) | The AI reads the prose and extracts facts + links                                | **Yes**                   |
| Realising "P-101" = "Pump 101"                          | Mostly maths (similarity); AI only for tricky cases                              | **Mostly no**             |

And where AI *is* used, it's fenced in: it must use our fixed vocabulary, its output must fit a strict form, **every fact is tied to the exact source sentence** (so it's checkable and powers the citations), low-confidence facts are flagged, and facts confirmed across multiple documents score higher. This protects accuracy, keeps everything trustworthy, and saves cost.

---

## 8. The build, layer by layer

Six levels. Each works on its own and adds to the last, so we always have something to show.

### Level 0 — Foundation

**What:** set up the workspace and the "vocabulary."
**How (plain):**

- Install the free databases/software with one command.
- Gather a realistic oil & gas document set covering **every type the brief names**: engineering drawings / P&IDs, maintenance work orders, safety procedures, inspection reports, operating instructions, project files, spreadsheets, scanned forms, and email archives — using real public sources (incident reports, OISD/OSHA rules, equipment manuals) plus realistic made-up maintenance records, quality records, and permits.
- Define the **vocabulary** (equipment, work orders, inspections, procedures, regulations, incidents, failure types, quality non-conformances, people, dates, and their links), based on real industry standards — and make it a **swappable profile** (oil & gas loaded first).
  **Done when:** software runs and the document set is ready.

### Level 1 — Read everything & pull out facts

**What:** turn messy documents into clean facts.
**How (plain):**

- Each document goes to the right reader: normal files to Docling; **drawings and scanned pages to the Computer-Vision step**, where the AI *looks at the image* and reads off the equipment tags, line numbers, and instrument tags (this is the "drawing digitisation" the brief asks for), with a quick **human-confirm screen** so the readings are trusted.
- The AI then extracts facts in a tidy form; structured files (spreadsheets, tables, quality records) are read directly by code.
- **Every extracted fact is stamped with two things:** the exact source passage it came from, and how confident the extraction was. These travel with the fact and feed the final confidence the user sees later.
- Each document is split into searchable passages tagged by meaning.
  **Done when:** a mixed folder produces clean facts + searchable passages (each carrying its source + confidence) — and **extraction accuracy is measured** (a judged metric).

### Level 2 — Build the web of connections

**What:** turn loose facts into the linked, asset-centric brain.
**How (plain):**

- Every fact becomes a dot; every relationship a link — and the **asset is the hub** everything else attaches to.
- **Matching duplicates properly (this is harder than it sounds, and we treat it seriously).** The same item shows up as "P-101", "Pump 101", or a tag on a drawing. We handle it in steps: normalise tags by their pattern, keep an **alias list**, use meaning-similarity to spot likely matches, and let the AI judge **only the genuinely unclear cases**, with a quick **human-confirm**. Crucially we *don't over-merge*: "P-101A" and "P-101B" are usually two different backup pumps, not one — so we keep them separate and record where every name came from.
- **Staying up to date is a real pipeline, not magic.** When a new document arrives: extract its facts → compare with what's already there → merge/resolve duplicates → update the web → refresh the affected "meaning fingerprints" → clear any now-stale cached answers. For the hackathon this runs as a repeatable "ingest new documents" step; a live, always-on version plugs into the same steps.
  **Done when:** we can view the web as a picture, **linkage completeness and duplicate-merging accuracy are measured** (judged metrics), and re-running ingestion on a new document correctly updates the web. The visual is a key demo moment.

### Level 3 — The Ask-Anything Copilot (centerpiece)

**What:** the chat where anyone gets a trustworthy answer. **The main demo.**
**How (plain):**

- It answers in clear steps (this is the real "GraphRAG" method, not just "search then AI"): **① spot what your question is about** (e.g., Pump P-101) → **② jump to it in the web and pull in its neighbours** (its work orders, the governing rule, the manual) → **③ also pull passages that match by meaning** → **④ combine both sets** → **⑤ write the answer.** Using the graph *and* meaning-search together is what lets it reason across departments.
- It writes a clear answer where **every claim shows the exact document/page (clickable)**.
- **The confidence level is built up, not guessed.** It's combined from: how sure we were when we *extracted* each fact (from Level 1), how solidly that fact is *linked* in the web, how well the *sources matched* the question, and whether **multiple documents agree**. When those are weak, the answer says so plainly instead of sounding falsely certain.
- It is **role-aware**: a technician, engineer, safety officer, and auditor each get answers framed for them, and sensitive personal data is only shown to those allowed to see it.
- It works on a phone, with answers streaming live.
- We deliberately test **cross-functional discovery**: questions whose best answer lives in *another department's* documents (e.g., a maintenance question answered by a safety procedure).
  **Done when:** it answers expert questions with correct sources, is **much faster than keyword search**, and we **measure cross-functional discovery** (all judged metrics). *This is a complete product on its own.*

### Level 4 — The smart assistants (what sets us apart)

**4a. Quality & Compliance assistant + QMS integration** (highest value):

- It works in a **hybrid** way, because real compliance is not a "vibe check" — "valve inspected every 6 months?" is an exact date check, not an opinion. So: the **AI first turns each regulation clause into a precise, checkable rule** (e.g., *"valves of this class → inspection every 6 months"*). Then a **plain-code checker** runs that rule against the actual records in the web and the dates/readings (last inspection date vs the 6-month limit, equipment state, any exceptions) and returns a hard **met / gap / unknown**. The AI is used to *read* the regulation and to *write the explanation* — but the **yes/no decision is made by exact code**, so it's reliable.
- It then produces an **audit-ready evidence package**, and — as the **QMS part** — it **flags quality deviations**, **raises non-conformance records**, and **drafts corrective-action workflows**, each tied to evidence. A simple **plug-in slot** lets it connect to a real QMS later via standard files/APIs.
  **Done when:** it produces a real evidence package on real regulations and **gap-detection accuracy is measured** (a judged metric).

**4b. Maintenance & Failure-Investigation (RCA) assistant:**

- For a piece of equipment, it pulls together work-order history, failure records, the manufacturer's manual, inspection findings, **and recent operating readings** (temperature, vibration, pressure). **How the readings get in (made concrete):** for the demo they come from a **replayed data file** kept in a simple **time-series table**, reached through a clean **"readings adapter."** In a real plant a live feed over the standard protocols **OPC-UA or MQTT** plugs into that *same adapter* — so it's designed-in, not bolted-on.
- It produces a **root-cause analysis** with evidence, **predictive maintenance recommendations**, and an **optimised maintenance schedule**.
  **Done when:** RCA matches known real causes and a sample optimised schedule is generated.

**4c. Lessons-Learned & proactive warnings:**

- It mines **the plant's own history first** — past incidents, near-misses, audit findings, and quality non-conformances — to find recurring patterns invisible to any single review. This internal history is the reliable core.
- It folds in **external incident reports (e.g., public investigation reports) only where they map cleanly onto our vocabulary** — because external data is often messy and inconsistent, we use it as a bonus, not a dependency.
- It **proactively pushes warnings** to the relevant team (an alert feed) **before** similar conditions recur, instead of waiting to be asked.
  **Done when:** it surfaces a real recurring pattern and pushes a matching warning.

### Level 5 — Prove it, polish it, present it

**What:** turn the working system into a winning submission.
**How (plain):**

- Build a **scorecard** measuring every judged metric (extraction accuracy, answer quality, linkage completeness, speed vs keyword search, compliance-gap accuracy, **cross-functional discovery**). Real numbers go into the deck.
- Add **role-based access** controls (who sees sensitive personal data) and make ingestion handle many documents smoothly (the **Scalability** story).
- Produce the **architecture diagram, slide deck, and demo video** (the four required deliverables).
  **Done when:** one command produces the scorecard, the demo is recorded, and the deck is ready.

> **Must-have line:** Levels 0–3 are a complete, demo-ready product. Levels 4–5 are the power that wins.

---

## 9. Two-week timeline

| Days   | Focus                                                                                                 |
| ------ | ----------------------------------------------------------------------------------------------------- |
| 1–2   | Level 0–1: setup, gather all document types, get reading + Computer-Vision + fact-extraction working |
| 3–4   | Level 2: build the auto-updating web + merge-duplicates                                               |
| 5–6   | Level 3: copilot — sources, confidence, role-aware, mobile, cross-functional discovery               |
| 7      | Level 4a: compliance + QMS (gaps, evidence packs, non-conformances, corrective actions)               |
| 8      | Level 4b: maintenance/RCA with live-conditions feed + optimised schedules                             |
| 9      | Level 4c: lessons-learned + proactive warnings                                                        |
| 10–12 | Level 5: scorecard, access control, architecture diagram, deck, demo video                            |
| 13–14 | Buffer for fixes and rehearsal                                                                        |

---

## 10. How we prove it works

The judges score on specific measurements, so we measure ourselves on the same ones from day one: extraction accuracy, answer quality, linkage completeness, speed vs old search, compliance-gap accuracy, and cross-functional discovery — all shown as real numbers, validated on real documents.

---

## 11. Why this wins

- Most teams will do "search over PDFs." We **connect knowledge across departments** — the actual point of the problem.
- **Every answer is trustworthy** (sources + confidence), and it's **role-aware** across functions.
- The assistants **do real work** — compliance + QMS, RCA with live conditions, proactive warnings.
- We use **real industrial documents** and bring **real numbers**, matching exactly how judges score.
- It runs **free and offline**, which doubles as a real-world selling point.

---

## 12. One design rule throughout

The "brain" (AI) sits behind a simple switch, so we can use the free online AI today, swap to a fully-offline one, or upgrade to a stronger paid model later (if the hackathon gives credits) — **without rewriting anything.** Same for the vocabulary (swap industries) and the QMS connection (plug in a real system later).
