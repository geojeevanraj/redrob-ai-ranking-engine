"""Job Intelligence Engine tests (LLM fully mocked)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.jobs.engine import JobExtractionError, JobIntelligenceEngine

VALID_JOB: dict[str, Any] = {
    "job_metadata": {
        "job_title": "Senior Backend Engineer",
        "company_name": "Acme",
        "employment_type": "full-time",
        "work_mode": "remote",
        "location": "Berlin",
        "industry": "SaaS",
    },
    "experience": {"minimum_years": 5, "seniority_level": "senior"},
    "education": {"required": ["BSc Computer Science"], "preferred": []},
    "required_skills": ["Python", "PostgreSQL"],
    "preferred_skills": ["Kubernetes"],
    "technical_stack": {
        "languages": ["Python"],
        "databases": ["PostgreSQL"],
        "devops": ["Docker", "Kubernetes"],
    },
    "responsibilities": ["Design APIs", "Mentor engineers"],
    "soft_skills": ["communication"],
    "leadership_expectations": [],
    "certifications": [],
    "benefits": ["Health insurance"],
    "salary": {"minimum": 80000, "maximum": 100000, "currency": "EUR", "period": "year"},
}


class FakeResponse:
    def __init__(
        self, data: dict[str, Any] | None, provider: str = "gemini", model: str = "gemini-1.5-flash"
    ) -> None:
        self.json_data = data
        self.provider = provider
        self.model = model


class FakeLLM:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls = 0

    async def generate_json(self, prompt: str, **kwargs: Any) -> FakeResponse:
        self.calls += 1
        return self.response


class FakePrompt:
    def get(self, key: str, version: Any = "latest", **values: Any) -> str:
        return "PROMPT:" + str(values.get("job_text", ""))


async def test_valid_extraction() -> None:
    engine = JobIntelligenceEngine(FakeLLM(FakeResponse(VALID_JOB)), FakePrompt())
    profile = await engine.parse("job description text")

    assert profile.job_metadata.job_title == "Senior Backend Engineer"
    assert profile.job_metadata.work_mode.value == "remote"
    assert profile.experience.minimum_years == 5
    assert "Python" in profile.required_skills
    assert "Kubernetes" in profile.preferred_skills
    assert profile.metadata.llm_provider == "gemini"
    assert profile.metadata.timestamp is not None


async def test_technology_stack_deduplicated() -> None:
    engine = JobIntelligenceEngine(FakeLLM(FakeResponse(VALID_JOB)), FakePrompt())
    profile = await engine.parse("job text")

    stack_lower = [t.lower() for t in profile.technology_stack]
    assert len(stack_lower) == len(set(stack_lower))  # no duplicates
    assert {"python", "postgresql", "docker", "kubernetes"}.issubset(set(stack_lower))


async def test_missing_fields_and_confidence() -> None:
    minimal = {"job_metadata": {}, "required_skills": [], "responsibilities": []}
    engine = JobIntelligenceEngine(FakeLLM(FakeResponse(minimal)), FakePrompt())
    profile = await engine.parse("job text")

    assert "job_title" in profile.metadata.missing_fields
    assert "required_skills" in profile.metadata.missing_fields
    assert profile.metadata.extraction_confidence < 0.5


async def test_empty_text_raises() -> None:
    engine = JobIntelligenceEngine(FakeLLM(FakeResponse(VALID_JOB)), FakePrompt())
    with pytest.raises(JobExtractionError):
        await engine.parse("   ")


async def test_no_json_raises() -> None:
    engine = JobIntelligenceEngine(FakeLLM(FakeResponse(None)), FakePrompt())
    with pytest.raises(JobExtractionError):
        await engine.parse("job text")


async def test_schema_validation_rejects_wrong_shape() -> None:
    bad = {"job_metadata": {}, "required_skills": "not a list", "responsibilities": []}
    engine = JobIntelligenceEngine(FakeLLM(FakeResponse(bad)), FakePrompt())
    with pytest.raises(JobExtractionError):
        await engine.parse("job text")


# ── Integration with the real LLM Manager (retry + fallback) ───────────────
async def test_fallback_to_secondary_on_malformed_primary() -> None:
    from ai.llm.manager import LLMManager
    from ai.tests.helpers import ScriptedProvider

    primary = ScriptedProvider("primary", text="this is not json")
    fallback = ScriptedProvider("fallback", text=json.dumps(VALID_JOB))
    manager = LLMManager(primary, fallback, max_retries=0)

    engine = JobIntelligenceEngine(manager, FakePrompt())
    profile = await engine.parse("job text")

    assert profile.job_metadata.job_title == "Senior Backend Engineer"
    assert profile.metadata.llm_provider == "fallback"


async def test_retry_then_fallback_with_rate_limit() -> None:
    from ai.llm.manager import LLMManager
    from ai.providers.exceptions import ProviderRateLimitError
    from ai.tests.helpers import ScriptedProvider

    primary = ScriptedProvider("primary", fail_with=ProviderRateLimitError)
    fallback = ScriptedProvider("fallback", text=json.dumps(VALID_JOB))
    manager = LLMManager(primary, fallback, max_retries=2)

    engine = JobIntelligenceEngine(manager, FakePrompt())
    profile = await engine.parse("job text")

    assert profile.metadata.llm_provider == "fallback"
    assert primary.calls == 3


async def test_all_providers_fail_propagates() -> None:
    from ai.llm.manager import LLMManager, LLMManagerError
    from ai.tests.helpers import ScriptedProvider

    primary = ScriptedProvider("primary", text="not json")
    fallback = ScriptedProvider("fallback", text="also not json")
    manager = LLMManager(primary, fallback, max_retries=0)

    engine = JobIntelligenceEngine(manager, FakePrompt())
    with pytest.raises(LLMManagerError):
        await engine.parse("job text")
