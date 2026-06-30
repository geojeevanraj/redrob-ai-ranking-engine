"""Response validator tests (text + JSON)."""

from __future__ import annotations

import pytest

from ai.llm.validation import extract_json, validate_json, validate_text
from ai.providers.exceptions import InvalidResponseError


def test_validate_text_ok() -> None:
    assert validate_text("hello") == "hello"


@pytest.mark.parametrize("bad", ["", "   ", "\n"])
def test_validate_text_rejects_empty(bad: str) -> None:
    with pytest.raises(InvalidResponseError):
        validate_text(bad)


def test_extract_plain_json() -> None:
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_fenced_json() -> None:
    text = '```json\n{\n  "a": 1\n}\n```'
    assert extract_json(text) == {"a": 1}


def test_extract_json_embedded_in_prose() -> None:
    text = 'Sure! Here it is: {"a": 1, "b": [1,2]} hope that helps.'
    assert extract_json(text) == {"a": 1, "b": [1, 2]}


@pytest.mark.parametrize("bad", ["", "not json", "{broken", "[1,2,3]"])
def test_extract_json_rejects_malformed(bad: str) -> None:
    with pytest.raises(InvalidResponseError):
        extract_json(bad)


def test_validate_json_required_keys() -> None:
    validate_json({"a": 1, "b": 2}, required_keys=["a", "b"])
    with pytest.raises(InvalidResponseError):
        validate_json({"a": 1}, required_keys=["a", "b"])
