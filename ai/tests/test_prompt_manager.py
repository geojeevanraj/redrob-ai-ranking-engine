"""Prompt manager tests (loading, versioning, rendering, validation)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai.prompts import PromptManager, PromptNotFoundError, PromptRenderError


@pytest.fixture
def prompts_dir(tmp_path: Path) -> Path:
    resume = tmp_path / "resume"
    resume.mkdir()
    (resume / "extract.v1.txt").write_text("Hello {{name}}", encoding="utf-8")
    (resume / "extract.v2.txt").write_text("Hi {{name}}, role {{role}}", encoding="utf-8")
    return tmp_path


def test_list_versions(prompts_dir: Path) -> None:
    pm = PromptManager(prompts_dir)
    assert pm.list_versions("resume/extract") == [1, 2]


def test_load_latest(prompts_dir: Path) -> None:
    pm = PromptManager(prompts_dir)
    template = pm.load("resume/extract")
    assert template.version == 2
    assert template.variables == {"name", "role"}


def test_load_specific_version(prompts_dir: Path) -> None:
    pm = PromptManager(prompts_dir)
    template = pm.load("resume/extract", version=1)
    assert template.version == 1


def test_render_substitutes_variables(prompts_dir: Path) -> None:
    pm = PromptManager(prompts_dir)
    rendered = pm.get("resume/extract", version=1, name="Ada")
    assert rendered == "Hello Ada"


def test_render_missing_variable_raises(prompts_dir: Path) -> None:
    pm = PromptManager(prompts_dir)
    with pytest.raises(PromptRenderError):
        pm.get("resume/extract", version=2, name="Ada")  # missing 'role'


def test_missing_prompt_raises(prompts_dir: Path) -> None:
    pm = PromptManager(prompts_dir)
    with pytest.raises(PromptNotFoundError):
        pm.load("resume/missing")


def test_literal_braces_are_preserved(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "json.v1.txt").write_text('Return JSON like {"name": "{{name}}"}', encoding="utf-8")
    pm = PromptManager(tmp_path)
    rendered = pm.get("shared/json", name="Ada")
    assert rendered == 'Return JSON like {"name": "Ada"}'
