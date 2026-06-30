"""Candidate Intelligence Engine tests (LLM fully mocked)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.candidates.engine import CandidateExtractionError, CandidateIntelligenceEngine

VALID_PROFILE: dict[str, Any] = {
    "personal_info": {"full_name": "Ada Lovelace", "email": "ada@x.io", "github": "ada"},
    "professional_summary": "Pioneering engineer.",
    "education": [{"institution": "Cambridge", "degree": "BSc"}],
    "experience": [
        {"company": "Analytical", "role": "Engineer", "technologies": ["Python", "FastAPI"]}
    ],
    "projects": [{"title": "Engine", "technologies": ["fastapi", "Docker"]}],
    "skills": {"programming_languages": ["Python", "python"], "devops": ["Docker"]},
    "certifications": [],
    "languages_known": ["English"],
}


class FakeResponse:
    def __init__(
        self, data: dict[str, Any] | None, provider: str = "gemini", model: str = "gemini-1.5-flash"
    ) -> None:
        self.json_data = data
        self.provider = provider
        self.model = model


class FakeLLM:
    """Returns a preset response from generate_json."""

    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls = 0

    async def generate_json(self, prompt: str, **kwargs: Any) -> FakeResponse:
        self.calls += 1
        return self.response


class FakePrompt:
    def get(self, key: str, version: Any = "latest", **values: Any) -> str:
        return "PROMPT:" + str(values.get("resume_text", ""))


async def test_valid_extraction() -> None:
    engine = CandidateIntelligenceEngine(FakeLLM(FakeResponse(VALID_PROFILE)), FakePrompt())
    profile = await engine.parse("resume text")

    assert profile.personal_info.full_name == "Ada Lovelace"
    assert profile.experience[0].company == "Analytical"
    assert profile.metadata.llm_provider == "gemini"
    assert profile.metadata.llm_model == "gemini-1.5-flash"
    assert profile.metadata.timestamp is not None


async def test_technology_stack_deduplicated() -> None:
    engine = CandidateIntelligenceEngine(FakeLLM(FakeResponse(VALID_PROFILE)), FakePrompt())
    profile = await engine.parse("resume text")

    stack_lower = [t.lower() for t in profile.technology_stack]
    assert len(stack_lower) == len(set(stack_lower))  # no duplicates
    assert {"python", "fastapi", "docker"}.issubset(set(stack_lower))


async def test_missing_fields_and_confidence() -> None:
    minimal = {"personal_info": {}, "experience": [], "skills": {}}
    engine = CandidateIntelligenceEngine(FakeLLM(FakeResponse(minimal)), FakePrompt())
    profile = await engine.parse("resume text")

    assert "full_name" in profile.metadata.missing_fields
    assert "experience" in profile.metadata.missing_fields
    assert profile.metadata.extraction_confidence < 0.5


async def test_empty_text_raises() -> None:
    engine = CandidateIntelligenceEngine(FakeLLM(FakeResponse(VALID_PROFILE)), FakePrompt())
    with pytest.raises(CandidateExtractionError):
        await engine.parse("   ")


async def test_no_json_raises() -> None:
    engine = CandidateIntelligenceEngine(FakeLLM(FakeResponse(None)), FakePrompt())
    with pytest.raises(CandidateExtractionError):
        await engine.parse("resume text")


async def test_schema_validation_rejects_wrong_shape() -> None:
    # `experience` must be a list; a string should fail schema validation.
    bad = {"personal_info": {}, "experience": "not a list", "skills": {}}
    engine = CandidateIntelligenceEngine(FakeLLM(FakeResponse(bad)), FakePrompt())
    with pytest.raises(CandidateExtractionError):
        await engine.parse("resume text")


# ── Integration with the real LLM Manager (retry + fallback) ───────────────
async def test_fallback_to_secondary_on_malformed_primary() -> None:
    from ai.llm.manager import LLMManager
    from ai.tests.helpers import ScriptedProvider

    primary = ScriptedProvider("primary", text="this is not json")
    fallback = ScriptedProvider("fallback", text=json.dumps(VALID_PROFILE))
    manager = LLMManager(primary, fallback, max_retries=0)

    engine = CandidateIntelligenceEngine(manager, FakePrompt())
    profile = await engine.parse("resume text")

    assert profile.personal_info.full_name == "Ada Lovelace"
    assert profile.metadata.llm_provider == "fallback"


async def test_retry_then_fallback_with_rate_limit() -> None:
    from ai.llm.manager import LLMManager
    from ai.providers.exceptions import ProviderRateLimitError
    from ai.tests.helpers import ScriptedProvider

    primary = ScriptedProvider("primary", fail_with=ProviderRateLimitError)
    fallback = ScriptedProvider("fallback", text=json.dumps(VALID_PROFILE))
    manager = LLMManager(primary, fallback, max_retries=2)

    engine = CandidateIntelligenceEngine(manager, FakePrompt())
    profile = await engine.parse("resume text")

    assert profile.metadata.llm_provider == "fallback"
    assert primary.calls == 3  # max_retries + 1 attempts before fallback


async def test_all_providers_fail_propagates() -> None:
    from ai.llm.manager import LLMManager, LLMManagerError
    from ai.tests.helpers import ScriptedProvider

    primary = ScriptedProvider("primary", text="not json")
    fallback = ScriptedProvider("fallback", text="also not json")
    manager = LLMManager(primary, fallback, max_retries=0)

    engine = CandidateIntelligenceEngine(manager, FakePrompt())
    with pytest.raises(LLMManagerError):
        await engine.parse("resume text")
