"""PDF extractor (PyMuPDF).

PyMuPDF is imported lazily so the module loads even when the dependency is
absent; a clear `ExtractionError` is raised at extraction time instead.
"""

from __future__ import annotations

from app.documents.exceptions import ExtractionError
from app.documents.extractors.base import ExtractionResult, TextExtractor
from app.documents.extractors.registry import register_extractor
from app.documents.model import DocumentFormat


@register_extractor(DocumentFormat.PDF)
class PdfExtractor(TextExtractor):
    """Extracts text per page from a PDF using PyMuPDF."""

    @property
    def document_format(self) -> DocumentFormat:
        return DocumentFormat.PDF

    def extract(self, content: bytes) -> ExtractionResult:
        try:
            import pymupdf
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise ExtractionError("PyMuPDF (pymupdf) is not installed") from exc

        try:
            doc = pymupdf.open(stream=content, filetype="pdf")
        except Exception as exc:
            raise ExtractionError(f"Could not open PDF: {exc}") from exc

        page_texts: list[str] = []
        try:
            for page in doc:
                page_texts.append(page.get_text("text"))
        finally:
            doc.close()

        return ExtractionResult(
            text="\f".join(page_texts),  # form-feed separates pages; cleaned later
            page_count=len(page_texts),
            page_texts=page_texts,
        )
