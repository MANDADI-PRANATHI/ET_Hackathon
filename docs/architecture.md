# Architecture — Unified Asset & Operations Brain

Everything runs locally and free. The "brain" (LLM) is the only swappable external
piece; everything else is open-source and on-device.

```mermaid
flowchart TB
  subgraph Ingest["1 · Ingest & Extract (Level 1)"]
    direction TB
    DOCS["Heterogeneous documents<br/>PDFs · P&IDs · spreadsheets · work orders ·<br/>inspections · permits · regulations · emails"]
    ROUTER{"Router by type"}
    STRUCT["Structured reader<br/>(CSV/tables — plain code)"]
    DOCLING["Docling<br/>(PDF/Office text + tables)"]
    VISION["Vision model<br/>(drawings / scans)"]
    PATTERNS["Regex patterns<br/>(tags, dates, reg refs)"]
    AIEX["AI extraction<br/>(facts from prose, with source + confidence)"]
    EMB["Local embeddings (BGE)<br/>meaning-fingerprints"]
    DOCS --> ROUTER
    ROUTER --> STRUCT & DOCLING & VISION
    DOCLING --> PATTERNS & AIEX & EMB
    VISION --> AIEX
  end

  subgraph Graph["2 · Knowledge Graph (Level 2)"]
    NEO[("Neo4j<br/>asset-centric graph + vector index")]
    RESOLVE["Entity resolution<br/>(merge P-101 = Pump 101)"]
    VALIDATE["Relationship validation<br/>(drop illegal links)"]
  end

  STRUCT --> RESOLVE
  AIEX --> VALIDATE
  PATTERNS --> RESOLVE
  RESOLVE --> NEO
  VALIDATE --> NEO
  EMB --> NEO

  subgraph Brain["LLM provider (swappable, $0)"]
    LLM["Gemini free tier<br/>or local Ollama"]
  end

  subgraph Apps["3 & 4 · Answers + Agents"]
    COPILOT["GraphRAG Copilot (L3)<br/>vector + graph traversal → cited answer + confidence"]
    COMPLY["Compliance checker (L4a)<br/>AI→rule, code decides, evidence pack"]
    RCA["RCA agent (L4b)<br/>graph history + sensor anomalies → root cause"]
  end

  READINGS[("Sensor readings feed<br/>CSV now · OPC-UA/MQTT in production")]

  NEO --> COPILOT & COMPLY & RCA
  READINGS --> RCA
  LLM -.-> AIEX & COPILOT & COMPLY & RCA
  COPILOT --> UI["Mobile web UI (L3b)<br/>FastAPI + chat page"]

  subgraph Eval["5 · Evaluation"]
    SCORE["Scorecard<br/>entity capture · linkage % · compliance P/R/F1 ·<br/>answer quality · time-to-answer"]
  end
  COPILOT --> SCORE
  COMPLY --> SCORE
  NEO --> SCORE
```

## The data stores (two layers)
- **Neo4j** — the connections store: the asset-centric graph **and** the vector index for meaning-search (one tool at hackathon scale; Qdrant is the scale-out path).
- **Postgres / MinIO** — app state and raw-file storage (local).

## Why each choice
- **Knowledge graph (Neo4j):** industrial documents are relationship-heavy; the graph is what lets the system reason *across* departments (the whole point of the problem).
- **Hybrid extraction:** plain code/rules for structured + predictable data; AI only for messy prose — more accurate, cheaper, every fact traceable to a source.
- **Hybrid compliance:** the AI turns regulations into checkable rules, but **plain code makes the pass/fail decision** — so compliance verdicts are reliable, not hallucinated.
- **Computed confidence:** built from retrieval score + source support + graph-fact confidence, not the model's self-report.
- **Local + swappable LLM:** runs free, and the offline option suits plants that can't send data to the cloud.
