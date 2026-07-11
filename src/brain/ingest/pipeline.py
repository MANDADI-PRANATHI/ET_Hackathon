"""The Level 1 pipeline: one messy folder in, clean source-stamped facts out.

For each file:
  route -> read -> extract facts -> chunk -> (optionally) embed -> stage as JSON

Extraction uses the cheapest reliable method per fact (structured columns and
regex identifiers need no AI; prose is left to the LLM), and every fact carries
its source and a confidence. The structured + regex path runs on Level 0 deps
alone, so `make ingest-structured` works before any heavy install.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from brain.ingest import extract as ai_extract
from brain.ingest.chunk import chunk_text
from brain.ingest.confidence import base
from brain.ingest.patterns import PatternExtractor, from_ontology
from brain.ingest.readers import document, drawing, structured, text
from brain.ingest.readers.base import StructuredResult, TextResult
from brain.ingest.router import DOCUMENT, DRAWING, STRUCTURED, TEXT, Route, route
from brain.schema import (
    AI, REGEX, VISION, Chunk, DocumentRecord, EdgeFact, NodeFact, SourceRef,
    StagedDoc,
)


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _mentions_from_chunk(
    chunk: Chunk, path: str, px: PatternExtractor, extractor_kind: str
) -> tuple[List[NodeFact], List[EdgeFact], List[str]]:
    """Deterministic (regex) facts from one passage: assets it names + which
    regulations it cites. Returns (nodes, edges, mentioned_asset_tags)."""
    needs_review = extractor_kind == VISION
    conf = base(extractor_kind)
    nodes: List[NodeFact] = []
    edges: List[EdgeFact] = []
    tags: List[str] = []
    found = px.find_clean(chunk.text)

    for m in found.get("equipment_tag", []):
        src = SourceRef(doc_id=chunk.doc_id, path=path, page=chunk.page,
                        evidence=chunk.text[:280])
        nodes.append(NodeFact(label="Asset", key="tag", value=m.normalized,
                              properties={"tag": m.normalized}, source=src,
                              confidence=conf, extractor=extractor_kind,
                              needs_review=needs_review, aliases=[m.surface]))
        edges.append(EdgeFact(type="MENTIONS", from_label="Chunk", from_value=chunk.id,
                              to_label="Asset", to_value=m.normalized, source=src,
                              confidence=conf, extractor=extractor_kind,
                              needs_review=needs_review))
        tags.append(m.normalized)

    for m in found.get("regulatory_reference", []):
        src = SourceRef(doc_id=chunk.doc_id, path=path, page=chunk.page,
                        evidence=chunk.text[:280])
        nodes.append(NodeFact(label="Regulation", key="code", value=m.normalized,
                              properties={"code": m.normalized}, source=src,
                              confidence=conf, extractor=extractor_kind,
                              needs_review=needs_review))
    return nodes, edges, tags


def _dedupe_nodes(nodes: List[NodeFact]) -> List[NodeFact]:
    """Collapse repeat (label,value) within one document, keeping the most
    confident and merging any non-null properties and aliases."""
    best: Dict[tuple, NodeFact] = {}
    for n in nodes:
        k = (n.label, n.value)
        cur = best.get(k)
        if cur is None:
            best[k] = n.model_copy(deep=True)
            continue
        if n.confidence > cur.confidence:
            cur.confidence = n.confidence
            cur.extractor = n.extractor
            cur.source = n.source
        for pk, pv in n.properties.items():
            if pv is not None and cur.properties.get(pk) in (None, ""):
                cur.properties[pk] = pv
        for a in n.aliases:
            if a not in cur.aliases:
                cur.aliases.append(a)
        cur.needs_review = cur.needs_review and n.needs_review
    return list(best.values())


def _read(rt: Route, vision_fn=None):
    if rt.reader_kind == STRUCTURED:
        return structured.read_structured(rt.path, rt.doc_id)
    if rt.reader_kind == TEXT:
        return text.read_text(rt.path, rt.doc_id)
    if rt.reader_kind == DOCUMENT:
        return document.read_document(rt.path, rt.doc_id)
    if rt.reader_kind == DRAWING:
        return drawing.read_drawing(rt.path, rt.doc_id, vision_fn=vision_fn)
    return None


def ingest_file(
    path: Path,
    corpus_root: Path,
    onto: Dict[str, Any],
    px: Optional[PatternExtractor] = None,
    llm=None,
    vision_fn=None,
    enable_vision: bool = True,
) -> Optional[StagedDoc]:
    rt = route(path, corpus_root)
    if not rt.reader_kind:
        return None
    # Drawings need the vision model; skip them when AI/vision is disabled
    # (e.g. the structured-only path) instead of forcing an API call.
    if rt.reader_kind == DRAWING and not enable_vision:
        return None
    px = px or from_ontology(onto)

    doc = DocumentRecord(id=rt.doc_id, doc_type=rt.doc_type, title=rt.title,
                         path=str(rt.path), ingested_at=_now())
    staged = StagedDoc(document=doc)
    read = _read(rt, vision_fn=vision_fn)
    if read is None:
        return None

    mentioned: set[str] = set()

    if isinstance(read, StructuredResult):
        staged.nodes.extend(read.nodes)
        staged.edges.extend(read.edges)
        for i, line in enumerate(read.row_texts):
            staged.chunks.append(Chunk(id=f"{rt.doc_id}::c{i}", doc_id=rt.doc_id,
                                       text=line, ordinal=i))
        mentioned.update(n.value for n in read.nodes if n.label == "Asset")
    elif isinstance(read, TextResult):
        staged.chunks = chunk_text(rt.doc_id, read.text, page_map=read.page_map)
        # A scanned PDF read via the vision-model fallback (document.py) is
        # stamped at the same low-confidence/needs-review tier as a drawing,
        # even though its reader_kind is DOCUMENT, not DRAWING.
        extractor_kind = (VISION if rt.reader_kind == DRAWING
                          or read.extractor_hint == "vision" else REGEX)
        for ch in staged.chunks:
            nodes, edges, tags = _mentions_from_chunk(ch, str(rt.path), px, extractor_kind)
            staged.nodes.extend(nodes)
            staged.edges.extend(edges)
            mentioned.update(tags)
            if llm is not None:
                src = SourceRef(doc_id=rt.doc_id, path=str(rt.path), page=ch.page,
                                evidence=ch.text[:280])
                anodes, aedges = ai_extract.extract_prose_facts(ch.text, src, onto, llm)
                staged.nodes.extend(anodes)
                staged.edges.extend(aedges)
                mentioned.update(n.value for n in anodes if n.label == "Asset")

    # The document is ABOUT every asset it discusses (asset-centric hub links).
    about_extractor_kind = (
        STRUCTURED if isinstance(read, StructuredResult) else
        VISION if rt.reader_kind == DRAWING
        or (isinstance(read, TextResult) and read.extractor_hint == "vision") else
        REGEX
    )
    about_src = SourceRef(doc_id=rt.doc_id, path=str(rt.path))
    about_conf = base(about_extractor_kind)
    for tag in sorted(mentioned):
        staged.edges.append(EdgeFact(type="ABOUT", from_label="Document",
                                     from_value=rt.doc_id, to_label="Asset",
                                     to_value=tag, source=about_src,
                                     confidence=about_conf,
                                     extractor=about_extractor_kind))
    # Chunk PART_OF Document
    for ch in staged.chunks:
        staged.edges.append(EdgeFact(type="PART_OF", from_label="Chunk", from_value=ch.id,
                                     to_label="Document", to_value=rt.doc_id,
                                     source=SourceRef(doc_id=rt.doc_id, path=str(rt.path),
                                                      page=ch.page),
                                     confidence=1.0, extractor=STRUCTURED))

    staged.nodes = _dedupe_nodes(staged.nodes)
    return staged



def _iter_files(corpus_root: Path) -> List[Path]:
    skip = {".gitkeep", ".md"}
    return [p for p in sorted(corpus_root.rglob("*"))
            if p.is_file() and p.suffix.lower() not in skip and p.name != "SOURCES.md"]


def ingest_corpus(
    corpus_root: Path,
    staging_dir: Path,
    onto: Dict[str, Any],
    use_ai: bool = False,
) -> Dict[str, int]:
    """Walk the corpus, stage every readable file, return summary counts."""
    corpus_root, staging_dir = Path(corpus_root), Path(staging_dir)
    px = from_ontology(onto)

    llm = None
    if use_ai:
        from brain.providers.llm import get_llm
        llm = get_llm()

    counts = {"documents": 0, "skipped": 0, "failed": 0,
              "nodes": 0, "edges": 0, "chunks": 0}
    failures = []
    for path in _iter_files(corpus_root):
        try:
            staged = ingest_file(path, corpus_root, onto, px=px, llm=llm,
                                 enable_vision=use_ai)
        except Exception as e:  # noqa: BLE001 - one bad file must not stop the batch
            counts["failed"] += 1
            failures.append((str(path), f"{type(e).__name__}: {e}"))
            continue
        if staged is None:
            counts["skipped"] += 1
            continue
        staged.write(staging_dir)
        counts["documents"] += 1
        counts["nodes"] += len(staged.nodes)
        counts["edges"] += len(staged.edges)
        counts["chunks"] += len(staged.chunks)
    if failures:
        print(f"  [warn] {len(failures)} file(s) could not be read (skipped):")
        for p, err in failures[:10]:
            print(f"    - {p}: {err}")
        if len(failures) > 10:
            print(f"    ... and {len(failures) - 10} more")
    return counts
