"""Parse PDFs / Office files into clean text with Docling (it organises layout
and tables — it does not invent content). Imported lazily.
"""
from __future__ import annotations

from pathlib import Path

from brain.config import settings


def parse_document(path: Path) -> str:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    # Born-digital PDFs (regulations, manuals) have real text -> no OCR needed.
    # Scanned/image PDFs go through the vision path instead. OCR stays off by
    # default (also avoids RapidOCR's model-download issues); flip DOCLING_OCR=true
    # in .env if you ever feed in a genuinely scanned PDF.
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = settings.docling_ocr

    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )
    result = converter.convert(str(path))
    return result.document.export_to_markdown()
