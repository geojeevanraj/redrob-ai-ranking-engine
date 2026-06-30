"""Language detection (detection only — no translation).

Uses `langdetect` with a fixed seed for deterministic results. Degrades
gracefully to ('unknown', 0.0) for empty/too-short text or detection failures.
"""

from __future__ import annotations

from app.documents.model import LanguageInfo

_MIN_CHARS = 20


def detect_language(text: str) -> LanguageInfo:
    """Detect the dominant language of `text` and its confidence."""
    stripped = text.strip()
    if len(stripped) < _MIN_CHARS:
        return LanguageInfo(language="unknown", confidence=0.0)

    try:
        from langdetect import DetectorFactory, detect_langs

        DetectorFactory.seed = 0
        results = detect_langs(stripped)
    except Exception:
        return LanguageInfo(language="unknown", confidence=0.0)

    if not results:
        return LanguageInfo(language="unknown", confidence=0.0)

    best = results[0]
    return LanguageInfo(language=best.lang, confidence=round(float(best.prob), 4))
