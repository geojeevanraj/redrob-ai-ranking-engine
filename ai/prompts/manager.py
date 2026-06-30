"""Prompt management system.

Prompts are stored as **versioned template files** organized into category
folders (resume/, jobs/, explainability/, copilot/, shared/). The
`PromptManager` loads them, substitutes variables, supports versioning, and
validates that every placeholder is filled.

Template syntax: variables use double braces, e.g. ``{{candidate_name}}``.
Double braces are used (instead of single) so prompt bodies can contain literal
JSON ``{ }`` without being treated as variables.

File naming convention:
    <category>/<name>.v<version>.txt        e.g. resume/extract.v1.txt
Resolution of ``version="latest"`` picks the highest numeric version found.

Sprint 1.1 ships the infrastructure only — no prompt content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_VARIABLE_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")
_FILENAME_PATTERN = re.compile(r"^(?P<name>.+)\.v(?P<version>\d+)\.txt$")


class PromptError(Exception):
    """Base error for prompt loading/rendering problems."""


class PromptNotFoundError(PromptError):
    """Requested prompt (or version) does not exist."""


class PromptRenderError(PromptError):
    """Rendering failed due to missing or extra variables."""


@dataclass(frozen=True)
class PromptTemplate:
    """A loaded, versioned prompt template."""

    key: str  # e.g. "resume/extract"
    version: int
    content: str
    path: Path

    @property
    def variables(self) -> set[str]:
        """Variable names referenced in the template body."""
        return set(_VARIABLE_PATTERN.findall(self.content))

    def render(self, **values: object) -> str:
        """Substitute variables, validating completeness.

        Raises `PromptRenderError` if required variables are missing or if any
        placeholder remains unfilled after substitution.
        """
        required = self.variables
        provided = set(values)
        missing = required - provided
        if missing:
            raise PromptRenderError(
                f"Missing variables for '{self.key}' v{self.version}: {sorted(missing)}"
            )

        def _replace(match: re.Match[str]) -> str:
            return str(values[match.group(1)])

        rendered = _VARIABLE_PATTERN.sub(_replace, self.content)
        leftover = _VARIABLE_PATTERN.findall(rendered)
        if leftover:
            raise PromptRenderError(f"Unfilled placeholders remain: {leftover}")
        return rendered


class PromptManager:
    """Loads and renders versioned prompt templates from a directory tree."""

    def __init__(self, prompts_dir: str | Path | None = None) -> None:
        self.prompts_dir = Path(prompts_dir) if prompts_dir else Path(__file__).parent
        self._cache: dict[tuple[str, int], PromptTemplate] = {}

    # ── Discovery ───────────────────────────────────────────────
    def list_versions(self, key: str) -> list[int]:
        """Return available version numbers for a prompt key, ascending."""
        target = self.prompts_dir / key
        parent = target.parent
        stem = target.name
        if not parent.is_dir():
            return []
        versions: list[int] = []
        for file in parent.iterdir():
            match = _FILENAME_PATTERN.match(file.name)
            if match and match.group("name") == stem:
                versions.append(int(match.group("version")))
        return sorted(versions)

    # ── Loading ─────────────────────────────────────────────────
    def load(self, key: str, version: int | str = "latest") -> PromptTemplate:
        """Load a prompt template by key and version ('latest' by default)."""
        resolved = self._resolve_version(key, version)
        cache_key = (key, resolved)
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self.prompts_dir / f"{key}.v{resolved}.txt"
        if not path.is_file():
            raise PromptNotFoundError(f"Prompt file not found: {path}")

        template = PromptTemplate(
            key=key,
            version=resolved,
            content=path.read_text(encoding="utf-8"),
            path=path,
        )
        self._cache[cache_key] = template
        return template

    def get(self, key: str, version: int | str = "latest", **values: object) -> str:
        """Convenience: load a template and render it in one call."""
        return self.load(key, version).render(**values)

    def _resolve_version(self, key: str, version: int | str) -> int:
        if isinstance(version, int):
            return version
        if version != "latest":
            raise PromptError(f"Invalid version '{version}' (use an int or 'latest')")
        versions = self.list_versions(key)
        if not versions:
            raise PromptNotFoundError(f"No versions found for prompt '{key}'")
        return versions[-1]
