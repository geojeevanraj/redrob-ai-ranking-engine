"""Job Intelligence Engine.

Converts a job description's clean text (from a `CanonicalDocument`) into a
validated `JobProfile` using the shared LLM Manager + Prompt Manager. The
original job description is never reprocessed — only its extracted clean text
is used.

IMPORTANT: extraction is strictly literal. The engine does NOT infer hidden
requirements, culture, leadership, or skills — that belongs to later sprints.

Like the Candidate engine, this depends on small structural `Protocol`s (not
concrete `ai` types) so it stays decoupled and easy to test with fakes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import ValidationError as PydanticValidationError

from app.jobs.schema import JobExtractionMetadata, JobProfile

# Top-level keys the LLM output must contain; missing keys make the LLM Manager
# treat the response as malformed and trigger retry/fallback.
_REQUIRED_KEYS = ["job_metadata", "required_skills", "responsibilities"]

# Key fields used to score extraction confidence + report missing fields.
_KEY_FIELDS = (
    "job_title",
    "company_name",
    "required_skills",
    "responsibilities",
    "experience",
    "technical_stack",
)

_SYSTEM_PROMPT = (
    "You are a precise job-description parser. Extract ONLY information that is "
    "explicitly stated. Respond with a single valid JSON object — no prose, no "
    "markdown fences. Use null for unknown scalar fields and empty arrays for "
    "unknown lists. Never infer hidden requirements, culture, leadership, or "
    "skills that are not literally written in the text."
)


class LLMResponseLike(Protocol):
    """Structural type for an LLM JSON response."""

    json_data: dict[str, Any] | None
    provider: str
    model: str


class LLMManagerLike(Protocol):
    """Structural type for the shared LLM Manager."""

    async def generate_json(
        self,
        prompt: str,
        *,
        system: str | None = ...,
        temperature: float = ...,
        max_tokens: int | None = ...,
        required_keys: list[str] | None = ...,
    ) -> LLMResponseLike: ...


class PromptManagerLike(Protocol):
    """Structural type for the shared Prompt Manager."""

    def get(self, key: str, version: int | str = ..., **values: object) -> str: ...


class JobExtractionError(Exception):
    """Raised when a job description cannot be converted into a valid JobProfile."""


class JobIntelligenceEngine:
    """Turns job-description clean text into a validated `JobProfile`."""

    def __init__(
        self,
        llm_manager: LLMManagerLike,
        prompt_manager: PromptManagerLike,
        *,
        prompt_key: str = "jobs/extract_profile",
        prompt_version: int | str = "latest",
    ) -> None:
        self.llm = llm_manager
        self.prompts = prompt_manager
        self.prompt_key = prompt_key
        self.prompt_version = prompt_version

    async def parse(self, clean_text: str) -> JobProfile:
        """Extract a structured profile from a job description's clean text."""
        if not clean_text or not clean_text.strip():
            raise JobExtractionError("Document has no text to parse")

        prompt = self.prompts.get(self.prompt_key, self.prompt_version, job_text=clean_text)
        response = await self.llm.generate_json(
            prompt,
            system=_SYSTEM_PROMPT,
            temperature=0.0,
            required_keys=_REQUIRED_KEYS,
        )

        data = response.json_data
        if not isinstance(data, dict):
            raise JobExtractionError("LLM returned no JSON object")

        try:
            profile = JobProfile.model_validate(data)
        except PydanticValidationError as exc:
            raise JobExtractionError(f"Profile failed schema validation: {exc}") from exc

        self._enrich(profile, provider=response.provider, model=response.model)
        return profile

    # ── Post-processing ─────────────────────────────────────
    def _enrich(self, profile: JobProfile, *, provider: str, model: str) -> None:
        profile.technology_stack = self._build_tech_stack(profile)
        missing = self._missing_fields(profile)
        profile.metadata = JobExtractionMetadata(
            extraction_confidence=self._confidence(missing),
            missing_fields=missing,
            warnings=[],
            llm_provider=provider,
            llm_model=model,
            timestamp=datetime.now(UTC),
        )

    @staticmethod
    def _build_tech_stack(profile: JobProfile) -> list[str]:
        """Deduplicate technologies from the categorized stack + skill lists."""
        seen: dict[str, str] = {}  # lowercase -> original casing
        sources: list[str] = [
            *profile.technical_stack.all_technologies(),
            *profile.required_skills,
            *profile.preferred_skills,
        ]
        for item in sources:
            key = item.strip().lower()
            if key and key not in seen:
                seen[key] = item.strip()
        return list(seen.values())

    @staticmethod
    def _missing_fields(profile: JobProfile) -> list[str]:
        missing: list[str] = []
        if not profile.job_metadata.job_title:
            missing.append("job_title")
        if not profile.job_metadata.company_name:
            missing.append("company_name")
        if not profile.required_skills:
            missing.append("required_skills")
        if not profile.responsibilities:
            missing.append("responsibilities")
        if profile.experience.minimum_years is None and not profile.experience.seniority_level:
            missing.append("experience")
        if not profile.technical_stack.all_technologies():
            missing.append("technical_stack")
        return missing

    @staticmethod
    def _confidence(missing: list[str]) -> float:
        present = len(_KEY_FIELDS) - len(missing)
        return round(max(0.0, present / len(_KEY_FIELDS)), 3)
