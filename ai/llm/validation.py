"""Reusable response validators.

Guards business logic from bad model output. Text validation ensures a
non-empty response; JSON validation extracts and parses JSON (tolerating
markdown code fences and surrounding prose) and rejects malformed output by
raising `InvalidResponseError` before it can reach any AI engine.
"""

from __future__ import annotations

import json
from typing import Any

from ai.providers.exceptions import InvalidResponseError


def validate_text(text: str, *, provider: str | None = None) -> str:
    """Return `text` if it is a non-empty string, else raise."""
    if not isinstance(text, str) or not text.strip():
        raise InvalidResponseError("Empty or non-text response", provider=provider)
    return text


def _strip_code_fences(text: str) -> str:
    """Remove a leading/trailing markdown code fence if present."""
    stripped = text.strip()
    if stripped.startswith("```"):
        # Drop the first fence line (``` or ```json) and the trailing fence.
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def extract_json(text: str, *, provider: str | None = None) -> dict[str, Any]:
    """Extract and parse a JSON object from model output.

    Handles raw JSON, fenced JSON (```json ... ```), and JSON embedded in
    surrounding prose by isolating the outermost `{ ... }` span. Raises
    `InvalidResponseError` if nothing valid can be parsed.
    """
    if not isinstance(text, str) or not text.strip():
        raise InvalidResponseError("Cannot parse JSON from empty response", provider=provider)

    candidate = _strip_code_fences(text)

    # First try a direct parse, then fall back to the outermost object span.
    for attempt in (candidate, _outermost_object(candidate)):
        if attempt is None:
            continue
        try:
            parsed = json.loads(attempt)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            raise InvalidResponseError("Expected a JSON object at the top level", provider=provider)
        return parsed

    raise InvalidResponseError("Response did not contain valid JSON", provider=provider)


def _outermost_object(text: str) -> str | None:
    """Return the substring spanning the first '{' to the last '}', if any."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def validate_json(
    data: dict[str, Any],
    *,
    required_keys: list[str] | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    """Validate a parsed JSON object, optionally enforcing required keys."""
    if not isinstance(data, dict):
        raise InvalidResponseError("Parsed JSON is not an object", provider=provider)
    if required_keys:
        missing = [k for k in required_keys if k not in data]
        if missing:
            raise InvalidResponseError(f"JSON missing required keys: {missing}", provider=provider)
    return data
