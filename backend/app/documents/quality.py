"""Heuristic quality metrics for extracted documents (no OCR performed).

These signals help downstream consumers decide whether a document is usable.
The OCR flag is *detection only* — no OCR is implemented in this sprint.
"""

from __future__ import annotations

from app.documents.extractors.base import ExtractionResult
from app.documents.model import QualityMetrics

# Below this average characters-per-page, a multi-page doc is likely scanned.
_OCR_CHARS_PER_PAGE_THRESHOLD = 30


def compute_quality(extraction: ExtractionResult, clean_text: str) -> QualityMetrics:
    """Derive quality metrics from an extraction result and cleaned text."""
    raw = extraction.text
    page_count = extraction.page_count
    empty_pages = extraction.empty_page_count

    if not raw.strip():
        return QualityMetrics(
            text_extraction_confidence=0.0,
            empty_page_count=empty_pages,
            ocr_required=page_count > 0,  # pages exist but no text => likely scanned
            malformed=True,
        )

    # Confidence blends printable-character ratio with the fraction of pages
    # that actually yielded text.
    printable = sum(1 for c in raw if c.isprintable() or c.isspace())
    printable_ratio = printable / len(raw)
    non_empty_pages = max(page_count - empty_pages, 0)
    page_factor = (non_empty_pages / page_count) if page_count else 1.0
    confidence = round(min(1.0, printable_ratio * page_factor), 3)

    avg_chars_per_page = (len(clean_text) / page_count) if page_count else len(clean_text)
    ocr_required = page_count > 0 and avg_chars_per_page < _OCR_CHARS_PER_PAGE_THRESHOLD

    return QualityMetrics(
        text_extraction_confidence=confidence,
        empty_page_count=empty_pages,
        ocr_required=ocr_required,
        malformed=False,
    )
