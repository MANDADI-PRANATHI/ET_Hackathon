"""Plain-text readers — .txt, .md, and .eml email archives (stdlib only).

These need no heavy dependencies, so structured-only ingestion (Level 0 deps)
can still read emails and notes, not just CSVs.
"""
from __future__ import annotations

from email import policy
from email.parser import BytesParser
from pathlib import Path

from brain.ingest.readers.base import TextResult

PLAIN_SUFFIXES = {".txt", ".md", ".text"}
EMAIL_SUFFIXES = {".eml"}


def is_plain(path: Path) -> bool:
    return path.suffix.lower() in PLAIN_SUFFIXES | EMAIL_SUFFIXES


def _read_email(path: Path) -> str:
    with path.open("rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)
    body_part = msg.get_body(preferencelist=("plain", "html"))
    body = body_part.get_content() if body_part else ""
    header = (
        f"Subject: {msg.get('subject', '')}\n"
        f"From: {msg.get('from', '')}\n"
        f"To: {msg.get('to', '')}\n"
        f"Date: {msg.get('date', '')}\n\n"
    )
    return header + body


def read_text(path: Path, _doc_id: str) -> TextResult:
    if path.suffix.lower() in EMAIL_SUFFIXES:
        return TextResult(text=_read_email(path))
    return TextResult(text=path.read_text(encoding="utf-8", errors="replace"))
