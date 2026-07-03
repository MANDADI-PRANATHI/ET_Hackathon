# Demo Script & Deck Outline — Sutradhar

Supports the two presentation deliverables: the **demo video** (script below) and
the **presentation deck** (slide-by-slide content). Everything here is real and
reproducible from the running system.

---

## Demo video script (~4 minutes)

**0:00 — The problem (15s).**
"In an asset-intensive plant, knowledge is scattered across 7–12 disconnected
systems. Engineers lose a third of their time hunting for it; incomplete history
drives 18–22% of unplanned downtime. We built Sutradhar — one brain that reads
every document and connects it around the asset."

**0:15 — Ingestion (30s).** `make synth && make ingest`
"We ingest work orders, inspections, incidents, emails, procedures. Structured
tables are read by code, identifiers by regex, prose by an LLM — every fact
stamped with its source and a confidence. No black box." Show
`python eval/extraction_eval.py` → **F1 1.0**.

**0:45 — The graph (30s).** `make build-graph`
"Facts merge into one asset-centric graph. PSV-110B is a single node built from 7
document types — maintenance, quality, safety, operations. And we don't
over-merge: P-101A and P-101B stay distinct backups." Show the `/ui` Graph tab —
the hub with its neighbours.

**1:15 — The copilot (60s).** Open `/ui`, ask by **voice**:
*"Is PSV-110B overdue for its statutory inspection?"*
"Answer with a **High confidence** badge, **clickable citations**, and a
**cross-functional** flag — the answer draws on inspection records, an email, and
an incident report. That's the whole point: knowledge crossing departments."
Switch role to Technician → personal names are redacted (PII gating).

**2:15 — Compliance agent (40s).** Compliance tab (or `make compliance`).
"The AI turns the OISD clause into a checkable rule, but **code** makes the
verdict: PSV-110B is **57 days past** its 6-month limit — a GAP, with evidence,
and an auto-drafted non-conformance and corrective action. An auditor can trust
the yes/no, not just the prose."

**2:55 — RCA agent (30s).** `make rca ASSET=P-101A`
"Why did P-101A fail? It fuses history with **live readings** — vibration
climbing 2.4 → 7.2 mm/s before the trip — names the degradation trend as the root
cause, and recommends acting before failure."

**3:25 — Lessons & warnings (20s).** Warnings tab.
"It mines history for recurring patterns and **pushes warnings** — the overdue
valve, the rising trend, a finding recurring across assets — before they escalate."

**3:45 — Scorecard + generality (15s).** Scorecard tab / `make scorecard`.
"Every metric the brief asks for, computed live. And the engine is
industry-generic — swap one file to run a manufacturing plant. Runs fully offline
on plant hardware. That's Sutradhar."

---

## Deck outline (10 slides, mapped to judging criteria)

1. **Title** — Sutradhar: the Unified Asset & Operations Brain. One line:
   "the thread-holder for your plant's knowledge."
2. **Problem** — 35% time lost · 18–22% downtime · 25% workforce retiring
   (the brief's own numbers). *Business Impact.*
3. **What it does** — read everything → connect around the asset → answer with
   trust → act (3 agents). One diagram (from ARCHITECTURE.md). *Innovation.*
4. **Ingestion** — hybrid extraction (code/regex/AI/vision), source + confidence
   on every fact. Metric: extraction F1 1.0. *Technical Excellence.*
5. **Knowledge graph** — asset-centric; cross-document merge; no over-merge;
   linkage 0.958. Show PSV-110B connected across 7 doc types. *Technical Excellence.*
6. **Copilot (GraphRAG)** — graph + meaning search; cited, confidence-scored,
   role-aware, voice, mobile. Cross-functional discovery 1.0. *Innovation + UX.*
7. **Compliance agent** — AI authors the rule, code decides. Evidence pack +
   auto CAPA. Gap-detection F1 1.0. *Business Impact.*
8. **RCA + Lessons** — live readings → root cause + predictive; proactive
   warnings before recurrence. *Business Impact + Innovation.*
9. **Scalability & offline** — swap one ontology file (oil&gas → manufacturing);
   OPC-UA/MQTT-ready readings adapter; runs fully offline on plant hardware.
   *Scalability.*
10. **Live scorecard** — every judged metric on one screen, generated live, not
    claimed. Close on the demo QR/link. *All criteria.*

---

## Reproduce every number

```bash
make up && make init && make synth      # infra + synthetic corpus + readings
make ingest                              # (or make ingest-structured on L0 deps)
make build-graph                         # asset-centric graph + linkage metric
make scorecard                           # all judged metrics, live
make api                                  # open http://localhost:8000/ui
make test                                 # 54 tests
```
