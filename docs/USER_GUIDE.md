# Sutradhar — User Guide

*For plant engineers, technicians, safety officers, auditors and operators.
No technical background needed.*

---

## What is Sutradhar?

Your plant produces thousands of documents — work orders, inspection reports,
incident reports, permits, regulations, manuals, emails. They live in different
systems, and nobody can quickly answer "what's the full story on pump P-101?"

Sutradhar reads all of them once, connects every fact to the piece of equipment
it's about, and lets you ask questions in plain English. Every answer comes with
**citations** (the exact source documents) and a **confidence score**, so you can
check the evidence instead of trusting a black box.

## Opening it

Ask your admin for the address — usually `http://<plant-server>:8000/ui/index.html`.
It works on desktop and mobile, in light and dark mode (toggle: ☾ button, top right).

---

## The tabs, one by one

### Ask — your starting point
Type a question the way you'd ask a colleague:

- *"Is PSV-110B overdue for inspection?"*
- *"Why did P-101A fail?"*
- *"Which assets have open non-conformances?"*

Before asking, **pick your role** (Viewing as…). The same fact is framed
differently for a technician ("what do I do") vs. an auditor ("what's the
evidence"), and personal data is hidden from roles that shouldn't see it.

Every answer shows:
- **The answer** — in plain language.
- **Confidence** — High / Medium / Low. High means multiple sources agree.
  Low means one weak mention: treat it as a lead to verify, not a fact.
- **Citations `[1] [2] …`** — each maps to a source snippet listed below the
  answer, with the file it came from.
- **A mode badge** — "cloud-polished" (a language model wrote the prose) or
  "local mode" (no internet needed; the same evidence, plainer wording).
  **The facts and citations are identical either way.**

On mobile you can tap the 🎙 microphone and speak your question.

### Overview
The dashboard: how much the brain currently knows (assets, passages), how many
compliance gaps and active warnings exist right now, and shortcuts to every
other tab.

### Knowledge Graph
Pick any equipment tag. You get:
- **Status cards** — needs attention or no open risks (computed from real open
  gaps/non-conformances, never guessed), last activity, document count,
  related equipment.
- **The connection ring** — everything linked to this asset: work orders,
  inspections, permits, incidents, regulations.
- **The asset timeline** — the asset's whole documented life in date order.
  Ideal before maintenance planning, RCA meetings, or audits.

### Compliance
Every asset checked against the regulation rules configured for your plant —
**MET** or **GAP**, decided by exact date arithmetic (not AI opinion). Gaps come
with an audit-ready evidence package and auto-drafted non-conformance +
corrective-action records. Check this before every audit.

### Warnings
Sutradhar pushes these to you — you don't have to ask. Overdue statutory
checks, rising sensor trends that match pre-failure patterns, and issues that
keep recurring across similar equipment. Worth a weekly look.

### Connect knowledge
Three ways to feed the brain — all live, no restart:
1. **Upload** — drag-and-drop a file, pick its category, done. Ask about it
   immediately.
2. **Sync a folder** — if your team already drops files into a shared/OneDrive/
   SharePoint folder, one click picks up everything new or changed.
3. **REST API** — for automated feeds (your admin sets this up).

### Scorecard
The system grading itself against its own benchmark — extraction accuracy,
answer quality, graph completeness. Numbers, not promises.

### How it works
A plain-language explanation of the pipeline, including exactly which parts
need an internet connection (few) and which never do (most).

---

## Five habits that get the most out of it

1. **Pick your role before asking** — the framing and privacy filtering depend on it.
2. **Read citations, not just the answer** — the answer is only as good as its sources.
3. **Respect the confidence label** — Low-confidence answers tell you what to verify.
4. **Feed it, then ask** — new documents are usable seconds after upload.
5. **It works offline** — if the plant's internet is down, answers keep coming
   with the same facts and citations.

## FAQ

**The answer looks wrong.** Check the citations — if the sources say something
different from the answer prose, trust the sources and report it. If the sources
themselves are wrong, the source document needs correcting; Sutradhar only knows
what the documents say.

**An asset is missing.** It appears once any ingested document mentions its tag.
Upload a document that references it (e.g. its register entry or a work order).

**"local mode" badge — is something broken?** No. It means the optional cloud
language model wasn't reachable, so the answer was composed locally from the
same cited evidence. Facts and citations are unaffected.
