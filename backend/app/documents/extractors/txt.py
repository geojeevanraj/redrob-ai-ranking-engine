"""Plain-text extractor."""

from __future__ import annotations

from app.documents.exceptions import ExtractionError
from app.documents.extractors.base import ExtractionResult, TextExtractor
from app.documents.extractors.registry import register_extractor
from app.documents.model import DocumentFormat


@register_extractor(DocumentFormat.TXT)
class TxtExtractor(TextExtractor):
    """Decodes raw bytes as text (UTF-8 with a latin-1 fallback)."""

    @property
    def document_format(self) -> DocumentFormat:
        return DocumentFormat.TXT

    def extract(self, content: bytes) -> ExtractionResult:
        warnings: list[str] = []
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("latin-1")
                warnings.append("decoded using latin-1 fallback")
            except UnicodeDecodeError as exc:  # pragma: no cover - extremely rare
                raise ExtractionError(f"Unable to decode text file: {exc}") from exc
        return ExtractionResult(
            text=text,
            page_count=1,
            page_texts=[text],
            warnings=warnings,
        )
