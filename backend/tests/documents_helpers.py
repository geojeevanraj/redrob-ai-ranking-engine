"""Helpers for document tests: generate real PDF/DOCX/TXT bytes in-memory."""

from __future__ import annotations

import io


def make_txt(text: str = "Hello world. This is a plain text document.") -> bytes:
    return text.encode("utf-8")


def make_pdf(lines: list[str] | None = None) -> bytes:
    """Create a simple one-page PDF with text using PyMuPDF."""
    import pymupdf

    lines = lines or ["Hello world from a PDF.", "This document has real text content."]
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line)
        y += 18
    data: bytes = doc.tobytes()
    doc.close()
    return data


def make_docx(paragraphs: list[str] | None = None) -> bytes:
    """Create a .docx with the given paragraphs using python-docx."""
    import docx

    paragraphs = paragraphs or ["Hello world from a DOCX.", "It contains paragraphs."]
    document = docx.Document()
    for p in paragraphs:
        document.add_paragraph(p)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()
