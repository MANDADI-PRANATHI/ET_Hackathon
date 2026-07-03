# Presentation Deck & Demo Video — outline

Maps to judging: **Innovation 25 · Business Impact 25 · Technical Excellence 20 · Scalability 15 · UX 15.**

## Slide-by-slide (≈10 slides)

1. **Title** — Unified Asset & Operations Brain · Problem Statement #8 · team name.

2. **The problem (Business Impact).** Plants run 7–12 disconnected document systems; ~35% of engineers' time lost searching; fragmentation drives 18–22% of unplanned downtime; the retiring-workforce "knowledge cliff." *One line: it's a safety, quality AND efficiency problem.*

3. **Our idea (Innovation).** Not search-over-PDFs — a **knowledge graph + RAG (GraphRAG)** that connects facts *across departments*, plus agents that *act*. Show the one-line contrast: plain RAG vs graph-grounded.

4. **Architecture (Technical Excellence).** The diagram from `docs/architecture.md`. Call out: hybrid extraction (code + AI), asset-centric graph, swappable $0 LLM.

5. **Demo 1 — Ask-anything Copilot.** Live on the phone: ask "Is P-101B overdue?" → cited answer + confidence badge + graph proofs. Stress **citations + computed confidence** (trustworthy, not a black box).

6. **Demo 2 — Connecting the dots (RCA).** `make rca ASSET=P-101B` → it fuses rising vibration + recurring alignments + open seal work order + overdue NCR into a root cause. *This is the headline: knowledge no single team holds.*

7. **Demo 3 — Compliance gap detection.** `make compliance` → catches the overdue PSV-110B deterministically + auto-generated audit evidence pack. Stress: **AI reads the rule, code makes the verdict** (reliable).

8. **Results (the scorecard).** The table from `reports/scorecard.md`: entity capture, linkage %, compliance P/R/F1, answer pass-rate + judge score, time-to-answer vs keyword search. *Real numbers — validated on real OSHA documents.*

9. **Scalability + cost.** Runs fully local & **$0**; offline-capable (a real selling point for plants that can't send data to cloud); swappable LLM and ontology profile (works for any asset-heavy plant, oil & gas is just the showcase); Neo4j→Qdrant scale path.

10. **Impact & roadmap.** Hours saved, downtime avoided, audit-ready compliance; next: lessons-learned engine, live OPC-UA/MQTT feed, more document types.

## Demo video script (≈3 minutes)
1. **0:00–0:20** — the problem in one sentence + what we built.
2. **0:20–0:30** — show the knowledge graph in Neo4j browser (the "web of connections" lighting up around an asset).
3. **0:30–1:10** — phone copilot: ask a question, point at the citations + confidence badge; ask a cross-department one to show it pulling from different silos.
4. **1:10–1:50** — RCA on P-101B: read the root cause; highlight the four data sources it connected.
5. **1:50–2:20** — compliance: catch PSV-110B, open the evidence pack.
6. **2:20–2:50** — the scorecard slide with real metrics; mention "validated on real OSHA documents, runs $0/offline."
7. **2:50–3:00** — one-line impact + close.

## Talking points (rehearse these)
- "Most teams stop at vector search; we built the **graph** — that's how it connects maintenance, sensors, quality and regulations no single person can."
- "Every answer shows its **source and a computed confidence** — and when it doesn't know, it says so."
- "Compliance verdicts are made by **code, not the AI** — so they're auditable."
- "It runs **free and offline** — which is exactly what real plants need for sensitive data."
