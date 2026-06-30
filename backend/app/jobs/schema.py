"""Canonical Job Profile schema.

The `JobProfile` is the structured, reusable representation of a Job Description
— the input contract for every downstream AI engine (Knowledge Graph, Hidden
Skill Inference, Decision Intelligence, Explainability).

IMPORTANT: this schema captures only information **explicitly present** in the
job description. No inference of hidden requirements, culture, leadership, or
skills happens here — that belongs to later sprints.

All fields default to empty so partial extractions still validate; the engine
records gaps in `metadata.missing_fields`.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    """Base with lenient parsing (ignore unknown keys from the LLM)."""

    model_config = ConfigDict(extra="ignore")


class WorkMode(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class JobMetadata(_Model):
    job_title: str | None = None
    company_name: str | None = None
    employment_type: str | None = None  # e.g. "full-time", "contract"
    work_mode: WorkMode = WorkMode.UNKNOWN
    location: str | None = None
    department: str | None = None
    industry: str | None = None


class ExperienceRequirement(_Model):
    minimum_years: float | None = None
    preferred_years: float | None = None
    seniority_level: str | None = None  # only if explicitly stated


class EducationRequirement(_Model):
    required: list[str] = Field(default_factory=list)
    preferred: list[str] = Field(default_factory=list)


class TechnicalStack(_Model):
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    libraries: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    cloud: list[str] = Field(default_factory=list)
    devops: list[str] = Field(default_factory=list)
    ai_ml: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)

    def all_technologies(self) -> list[str]:
        """Flatten every technology category into one list (order-preserving)."""
        return [
            *self.languages,
            *self.frameworks,
            *self.libraries,
            *self.databases,
            *self.cloud,
            *self.devops,
            *self.ai_ml,
            *self.tools,
        ]


class SalaryInfo(_Model):
    minimum: float | None = None
    maximum: float | None = None
    currency: str | None = None
    period: str | None = None  # e.g. "year", "month", "hour"
    raw: str | None = None  # original salary text if present


class JobExtractionMetadata(_Model):
    """Engine-computed metadata (not produced by the LLM)."""

    extraction_confidence: float = 0.0
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    llm_provider: str | None = None
    llm_model: str | None = None
    timestamp: datetime | None = None


class JobProfile(_Model):
    """Structured job profile extracted from a job description."""

    job_metadata: JobMetadata = Field(default_factory=JobMetadata)
    experience: ExperienceRequirement = Field(default_factory=ExperienceRequirement)
    education: EducationRequirement = Field(default_factory=EducationRequirement)

    # Explicit must-have vs. nice-to-have skills.
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)

    technical_stack: TechnicalStack = Field(default_factory=TechnicalStack)
    responsibilities: list[str] = Field(default_factory=list)

    # Only explicitly mentioned — never inferred.
    soft_skills: list[str] = Field(default_factory=list)
    leadership_expectations: list[str] = Field(default_factory=list)

    certifications: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    salary: SalaryInfo = Field(default_factory=SalaryInfo)

    # Deduplicated, flattened technology list (engine-computed).
    technology_stack: list[str] = Field(default_factory=list)

    # Engine-computed extraction metadata.
    metadata: JobExtractionMetadata = Field(default_factory=JobExtractionMetadata)
