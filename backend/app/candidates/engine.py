"""Candidate Intelligence Engine.

Converts a resume's clean text (from a `CanonicalDocument`) into a validated
`CandidateProfile` using the shared LLM Manager + Prompt Manager. The original
PDF is never reprocessed — only the previously extracted clean text is used.

The engine depends on small structural `Protocol`s (not concrete `ai` types) so
it stays decoupled and easy to test with fakes; the real `ai.llm.LLMManager`
and `ai.prompts.PromptManager` satisfy these protocols by duck typing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import ValidationError as PydanticValidationError

from app.candidates.schema import CandidateProfile, ExtractionMetadata

# Top-level keys the LLM output must contain; missing keys make the LLM Manager
# treat the response as malformed and trigger retry/fallback.
_REQUIRED_KEYS = ["personal_info", "experience", "skills"]

# Key fields used to score extraction confidence + report missing fields.
_KEY_FIELDS = (
    "full_name",
    "email",
    "professional_summary",
    "education",
    "experience",
    "projects",
    "skills",
)

_SYSTEM_PROMPT = (
    "You are a precise resume parser. Extract structured data and respond with "
    "a single valid JSON object only — no prose, no markdown fences. Use null "
    "for unknown scalar fields and empty arrays for unknown lists. Never invent "
    "information that is not present in the resume."
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


class CandidateExtractionError(Exception):
    """Raised when a resume cannot be converted into a valid CandidateProfile."""


class CandidateIntelligenceEngine:
    """Turns resume clean text into a validated `CandidateProfile`."""

    def __init__(
        self,
        llm_manager: LLMManagerLike,
        prompt_manager: PromptManagerLike,
        *,
        prompt_key: str = "resume/extract_profile",
        prompt_version: int | str = "latest",
    ) -> None:
        self.llm = llm_manager
        self.prompts = prompt_manager
        self.prompt_key = prompt_key
        self.prompt_version = prompt_version

    async def parse(self, clean_text: str) -> CandidateProfile:
        """Extract a structured profile from a resume's clean text."""
        if not clean_text or not clean_text.strip():
            raise CandidateExtractionError("Document has no text to parse")

        prompt = self.prompts.get(self.prompt_key, self.prompt_version, resume_text=clean_text)
        response = await self.llm.generate_json(
            prompt,
            system=_SYSTEM_PROMPT,
            temperature=0.0,
            required_keys=_REQUIRED_KEYS,
        )

        data = response.json_data
        if not isinstance(data, dict):
            raise CandidateExtractionError("LLM returned no JSON object")

        try:
            profile = CandidateProfile.model_validate(data)
        except PydanticValidationError as exc:
            raise CandidateExtractionError(f"Profile failed schema validation: {exc}") from exc

        self._enrich(profile, provider=response.provider, model=response.model)
        return profile

    # ── Post-processing ─────────────────────────────────────
    def _enrich(self, profile: CandidateProfile, *, provider: str, model: str) -> None:
        profile.technology_stack = self._build_tech_stack(profile)
        missing = self._missing_fields(profile)
        profile.metadata = ExtractionMetadata(
            extraction_confidence=self._confidence(missing),
            missing_fields=missing,
            warnings=[],
            llm_provider=provider,
            llm_model=model,
            timestamp=datetime.now(UTC),
        )

    @staticmethod
    def _build_tech_stack(profile: CandidateProfile) -> list[str]:
        """Deduplicate technologies from skills, experience, and projects."""
        seen: dict[str, str] = {}  # lowercase -> original casing
        sources: list[str] = list(profile.skills.all_skills())
        for exp in profile.experience:
            sources.extend(exp.technologies)
        for proj in profile.projects:
            sources.extend(proj.technologies)
        for item in sources:
            key = item.strip().lower()
            if key and key not in seen:
                seen[key] = item.strip()
        return list(seen.values())

    @staticmethod
    def _missing_fields(profile: CandidateProfile) -> list[str]:
        missing: list[str] = []
        if not profile.personal_info.full_name:
            missing.append("full_name")
        if not profile.personal_info.email:
            missing.append("email")
        if not profile.professional_summary:
            missing.append("professional_summary")
        if not profile.education:
            missing.append("education")
        if not profile.experience:
            missing.append("experience")
        if not profile.projects:
            missing.append("projects")
        if not profile.skills.all_skills():
            missing.append("skills")
        return missing

    @staticmethod
    def _confidence(missing: list[str]) -> float:
        present = len(_KEY_FIELDS) - len(missing)
        return round(max(0.0, present / len(_KEY_FIELDS)), 3)
