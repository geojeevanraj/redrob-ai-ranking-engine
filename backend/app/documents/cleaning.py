"""Generic, composable text-cleaning pipeline.

Each processor is a small, reusable transformation with a stable `name`. The
`CleaningPipeline` runs an ordered list of processors. Nothing here is
business-specific — these are generic normalizers usable by any document type.

Default order:
    line endings -> unicode (NFKC) -> page markers -> header/footer
    -> whitespace collapse -> duplicate blank lines -> trim
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import ClassVar, Protocol, runtime_checkable


@runtime_checkable
class TextProcessor(Protocol):
    """A single text transformation step."""

    name: str

    def process(self, text: str) -> str: ...


class LineEndingNormalizer:
    """Normalize CRLF/CR to LF and drop form-feed page separators."""

    name = "line_endings"

    def process(self, text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")


class UnicodeNormalizer:
    """Apply Unicode NFKC normalization (compatibility + composition)."""

    name = "unicode_nfkc"

    def process(self, text: str) -> str:
        return unicodedata.normalize("NFKC", text)


class PageMarkerRemover:
    """Remove standalone page numbers and common page markers."""

    name = "page_markers"
    _PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"^\s*\d{1,4}\s*$"),  # bare page number line
        re.compile(r"^\s*page\s+\d+(\s+of\s+\d+)?\s*$", re.IGNORECASE),
        re.compile(r"^\s*\d+\s*/\s*\d+\s*$"),  # "3 / 12"
        re.compile(r"^\s*[-\u2013\u2014]\s*\d+\s*[-\u2013\u2014]\s*$"),  # "- 3 -"
    ]

    def process(self, text: str) -> str:
        kept = [line for line in text.split("\n") if not any(p.match(line) for p in self._PATTERNS)]
        return "\n".join(kept)


class HeaderFooterRemover:
    """Remove short lines that repeat across the document (likely headers/footers).

    Generic heuristic: a short line (< `max_len` chars) appearing at least
    `min_repeats` times is treated as boilerplate and removed.
    """

    name = "header_footer"

    def __init__(self, *, min_repeats: int = 3, max_len: int = 80) -> None:
        self.min_repeats = min_repeats
        self.max_len = max_len

    def process(self, text: str) -> str:
        lines = text.split("\n")
        counts = Counter(line.strip() for line in lines if line.strip())
        boilerplate = {
            line
            for line, count in counts.items()
            if count >= self.min_repeats and len(line) <= self.max_len
        }
        if not boilerplate:
            return text
        return "\n".join(line for line in lines if line.strip() not in boilerplate)


class WhitespaceCollapser:
    """Collapse runs of intra-line spaces/tabs to a single space."""

    name = "whitespace"
    _RUN = re.compile(r"[ \t]+")

    def process(self, text: str) -> str:
        return "\n".join(self._RUN.sub(" ", line) for line in text.split("\n"))


class DuplicateEmptyLineRemover:
    """Collapse 2+ consecutive blank lines into a single blank line."""

    name = "duplicate_blank_lines"
    _RUN = re.compile(r"\n{3,}")

    def process(self, text: str) -> str:
        return self._RUN.sub("\n\n", text)


class Trimmer:
    """Trim trailing spaces per line and surrounding whitespace overall."""

    name = "trim"

    def process(self, text: str) -> str:
        return "\n".join(line.rstrip() for line in text.split("\n")).strip()


class CleaningPipeline:
    """Runs an ordered sequence of text processors."""

    def __init__(self, processors: list[TextProcessor]) -> None:
        self.processors = processors

    def run(self, text: str) -> str:
        for processor in self.processors:
            text = processor.process(text)
        return text

    @property
    def steps(self) -> list[str]:
        return [p.name for p in self.processors]


def default_pipeline() -> CleaningPipeline:
    """Return the standard generic cleaning pipeline."""
    return CleaningPipeline(
        [
            LineEndingNormalizer(),
            UnicodeNormalizer(),
            PageMarkerRemover(),
            HeaderFooterRemover(),
            WhitespaceCollapser(),
            DuplicateEmptyLineRemover(),
            Trimmer(),
        ]
    )
