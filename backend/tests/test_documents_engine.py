"""Tests for the Document Intelligence Engine and its sub-components."""

from __future__ import annotations

import pytest

from app.documents import DocumentIntelligenceEngine, ProcessingStatus
from app.documents.engine import format_from_filename
from app.documents.exceptions import UnsupportedFormatError
from app.documents.metadata import compute_checksum
from app.documents.model import DocumentFormat
from tests.documents_helpers import make_docx, make_pdf, make_txt

engine = DocumentIntelligenceEngine()


def test_format_from_filename() -> None:
    assert format_from_filename("resume.PDF") is DocumentFormat.PDF
    assert format_from_filename("a.b.docx") is DocumentFormat.DOCX
    assert format_from_filename("notes.txt") is DocumentFormat.TXT


def test_unsupported_format_raises() -> None:
    with pytest.raises(UnsupportedFormatError):
        format_from_filename("image.png")


def test_checksum_is_deterministic_and_changes_with_content() -> None:
    a = compute_checksum(b"hello")
    assert a == compute_checksum(b"hello")
    assert a != compute_checksum(b"world")
    assert len(a) == 64


def test_process_txt() -> None:
    doc = engine.process(make_txt("Hello world. Plain text here."), filename="n.txt")
    assert doc.processing_status is ProcessingStatus.COMPLETED
    assert "Hello world" in doc.clean_text
    assert doc.metadata.extension == "txt"
    assert doc.metadata.word_count > 0
    assert doc.metadata.char_count > 0
    assert doc.quality.malformed is False


def test_process_pdf_extracts_text() -> None:
    doc = engine.process(make_pdf(), filename="doc.pdf")
    assert doc.processing_status is ProcessingStatus.COMPLETED
    assert "Hello world" in doc.clean_text
    assert doc.metadata.page_count >= 1
    assert doc.quality.text_extraction_confidence > 0.0


def test_process_docx_extracts_text() -> None:
    doc = engine.process(make_docx(["First para.", "Second para."]), filename="doc.docx")
    assert doc.processing_status is ProcessingStatus.COMPLETED
    assert "First para" in doc.clean_text
    assert doc.metadata.mime_type.endswith("wordprocessingml.document")


def test_malformed_pdf_marked_failed() -> None:
    doc = engine.process(b"%PDF-not-really-a-pdf", filename="broken.pdf")
    assert doc.processing_status is ProcessingStatus.FAILED
    assert doc.quality.malformed is True
    assert doc.warnings


def test_language_detection_english() -> None:
    text = (
        "This is a reasonably long English sentence used to detect the language "
        "with a good degree of confidence for testing purposes."
    )
    doc = engine.process(make_txt(text), filename="en.txt")
    assert doc.language.language == "en"
    assert doc.language.confidence > 0.5


def test_language_unknown_for_short_text() -> None:
    doc = engine.process(make_txt("hi"), filename="short.txt")
    assert doc.language.language == "unknown"
    assert doc.language.confidence == 0.0


def test_metadata_counts_match_clean_text() -> None:
    doc = engine.process(make_txt("one two three four"), filename="c.txt")
    assert doc.metadata.word_count == 4
    assert doc.metadata.char_count == len(doc.clean_text)
