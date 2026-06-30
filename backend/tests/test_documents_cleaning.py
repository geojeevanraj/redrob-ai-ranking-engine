"""Unit tests for the generic cleaning processors and pipeline."""

from __future__ import annotations

from app.documents.cleaning import (
    DuplicateEmptyLineRemover,
    HeaderFooterRemover,
    LineEndingNormalizer,
    PageMarkerRemover,
    Trimmer,
    UnicodeNormalizer,
    WhitespaceCollapser,
    default_pipeline,
)


def test_line_ending_normalizer() -> None:
    assert LineEndingNormalizer().process("a\r\nb\rc\fd") == "a\nb\nc\nd"


def test_unicode_normalizer() -> None:
    # Fullwidth characters normalize to ASCII under NFKC.
    assert UnicodeNormalizer().process("ＡＢＣ") == "ABC"


def test_whitespace_collapser() -> None:
    assert WhitespaceCollapser().process("a    b\t\tc") == "a b c"


def test_duplicate_empty_line_remover() -> None:
    assert DuplicateEmptyLineRemover().process("a\n\n\n\nb") == "a\n\nb"


def test_page_marker_remover() -> None:
    text = "Intro\n3\nPage 2 of 10\n- 5 -\n2 / 12\nReal content"
    cleaned = PageMarkerRemover().process(text)
    assert "Real content" in cleaned
    assert "Page 2 of 10" not in cleaned
    assert "- 5 -" not in cleaned
    assert "\n3\n" not in f"\n{cleaned}\n"


def test_header_footer_remover() -> None:
    text = "\n".join(
        [
            "ACME CONFIDENTIAL",
            "body 1",
            "ACME CONFIDENTIAL",
            "body 2",
            "ACME CONFIDENTIAL",
            "body 3",
        ]
    )
    cleaned = HeaderFooterRemover(min_repeats=3, max_len=80).process(text)
    assert "ACME CONFIDENTIAL" not in cleaned
    assert "body 1" in cleaned and "body 3" in cleaned


def test_trimmer() -> None:
    assert Trimmer().process("  a   \n  b  \n  ") == "a\n  b"


def test_default_pipeline_end_to_end() -> None:
    raw = "ＨＥＬＬＯ\r\n\r\n\r\n1\nworld   text\fpage\n\n\n"
    cleaned = default_pipeline().run(raw)
    assert "HELLO" in cleaned
    assert "world text" in cleaned
    assert "\n\n\n" not in cleaned
    assert not cleaned.endswith("\n")


def test_pipeline_exposes_steps() -> None:
    steps = default_pipeline().steps
    assert steps[0] == "line_endings"
    assert "trim" in steps
