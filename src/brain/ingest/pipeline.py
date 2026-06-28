"""Routes each file in the corpus to the right reader, runs layered extraction,
and writes one staging JSON per document (Level 2 loads these into the graph).

  structured CSV -> direct parser (no AI)
  text / PDF      -> regex tags + chunks + (optional) AI prose extraction
  image / drawing -> vision model
"""
from __future__ import annotations

import json
import pathlib
from typing import Optional

from brain.ingest import structured
from brain.ingest.models import Chunk, DocFacts, ExtractedEntity
from brain.ingest.patterns import find_matches

STRUCTURED = {
    "asset_register.csv": structured.parse_asset_register,
    "work_orders.csv": structured.parse_work_orders,
    "inspections.csv": structured.parse_inspections,
    "permits.csv": structured.parse_permits,
    "nonconformances.csv": structured.parse_nonconformances,
}
TEXT_EXT = {".txt", ".md", ".eml", ".pdf", ".docx"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
SKIP = {"SOURCES.md", ".gitkeep"}


def ingest_file(path: pathlib.Path, use_ai: bool = True, use_embeddings: bool = True) -> Optional[DocFacts]:
    name, ext = path.name.lower(), path.suffix.lower()
    if path.name in STRUCTURED or name in STRUCTURED:
        return STRUCTURED[name](path)
    if ext in TEXT_EXT:
        return _ingest_text(path, use_ai, use_embeddings)
    if ext in IMAGE_EXT:
        return _ingest_image(path, use_ai)
    return None


def _ingest_text(path: pathlib.Path, use_ai: bool, use_embeddings: bool) -> DocFacts:
    df = DocFacts(path.name, "Document", str(path))
    if path.suffix.lower() in {".pdf", ".docx"}:
        from brain.ingest.documents import parse_document
        text = parse_document(path)
    else:
        text = path.read_text(encoding="utf-8", errors="ignore")

    # 1) deterministic tags (no AI)
    for tag in find_matches(text).get("equipment_tag", []):
        df.entities.append(ExtractedEntity("Asset", tag, source=path.name, confidence=0.9, method="rule"))

    # 2) passages (+ optional local embeddings)
    from brain.ingest.chunking import split_text
    texts = split_text(text)
    if use_embeddings and texts:
        from brain.ingest.chunking import embed_chunks
        df.chunks = embed_chunks(df.document_id, texts)
    else:
        df.chunks = [Chunk(id=f"{df.document_id}::{i}", text=t) for i, t in enumerate(texts)]

    # 3) AI extraction from prose
    if use_ai and text.strip():
        from brain.ingest.llm_extract import extract_from_text
        ents, rels = extract_from_text(text, path.name)
        df.entities.extend(ents)
        df.relations.extend(rels)
    return df


def _ingest_image(path: pathlib.Path, use_ai: bool) -> DocFacts:
    df = DocFacts(path.name, "PID", str(path))
    if use_ai:
        from brain.ingest.vision import read_drawing
        for tag in read_drawing(path).get("tags", []):
            df.entities.append(
                ExtractedEntity("Asset", str(tag), source=f"{path.name} (vision)",
                                confidence=0.7, method="vision"))
    return df


def run(corpus_dir: str = "data/corpus", staging_dir: str = "data/staging",
        use_ai: bool = True, use_embeddings: bool = True) -> None:
    corpus = pathlib.Path(corpus_dir)
    staging = pathlib.Path(staging_dir)
    staging.mkdir(parents=True, exist_ok=True)

    docs = ent = rel = chk = 0
    print(f"Ingesting {corpus}  (AI={use_ai}, embeddings={use_embeddings})\n")
    for path in sorted(corpus.rglob("*")):
        if not path.is_file() or path.name in SKIP:
            continue
        try:
            facts = ingest_file(path, use_ai, use_embeddings)
        except Exception as e:  # one bad file must not kill the whole run
            print(f"  !! error on {path.relative_to(corpus)}: {type(e).__name__}: {e}")
            continue
        if facts is None:
            print(f"  -- skipped (no reader): {path.relative_to(corpus)}")
            continue
        out = staging / f"{facts.document_id}.json"
        out.write_text(json.dumps(facts.to_dict(), indent=2, default=str), encoding="utf-8")
        e, r, c = len(facts.entities), len(facts.relations), len(facts.chunks)
        docs, ent, rel, chk = docs + 1, ent + e, rel + r, chk + c
        print(f"  {path.relative_to(corpus)}: {e} entities, {r} relations, {c} chunks")

    print(f"\n{docs} documents -> {ent} entities, {rel} relations, {chk} chunks")
    print(f"Staging written to: {staging}/")
