"""Level 1 — read documents and pull out facts (entities, relations, chunks).

Layered extraction:
  - structured.py : CSV / tables read directly by code (no AI)
  - patterns.py   : predictable codes (tags, dates, reg refs) via regex (no AI)
  - documents.py  : PDFs/Office parsed by Docling
  - vision.py     : drawings/scanned pages read by the vision model
  - llm_extract.py: facts buried in prose, extracted by the AI (with source + confidence)
  - chunking.py   : split into passages + local embeddings
  - pipeline.py   : routes each file to the right reader and writes staging output
"""
