"""Canonical Candidate Profile schema.

The `CandidateProfile` is the structured, reusable representation of a resume —
the input contract for every later AI engine (hidden skills, DNA, ranking, …).
All fields default to empty so partial extractions still validate; the engine
records what was missing in `metadata.missing_fields`.

Dates are kept as free-form strings because resumes are wildly inconsistent;
normalization (if ever needed) is a separate concern.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    """Base with lenient parsing (ignore unknown keys from the LLM)."""

    model_config = ConfigDict(extra="ignore")


class PersonalInfo(_Model):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None


class EducationEntry(_Model):
    institution: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    grade: str | None = None
    details: str | None = None


class ExperienceEntry(_Model):
    company: str | None = None
    role: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    business_impact: str | None = None


class ProjectEntry(_Model):
    title: str | None = None
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    domain: str | None = None
    impact: str | None = None
    team_size: int | None = None


class Skills(_Model):
    programming_languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    libraries: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    cloud: list[str] = Field(default_factory=list)
    devops: list[str] = Field(default_factory=list)
    ai_ml: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)

    def all_skills(self) -> list[str]:
        """Flatten every skill category into one list (order-preserving)."""
        return [
            *self.programming_languages,
            *self.frameworks,
            *self.libraries,
            *self.databases,
            *self.cloud,
            *self.devops,
            *self.ai_ml,
            *self.tools,
        ]


class ExtractionMetadata(_Model):
    """Engine-computed metadata (not produced by the LLM)."""

    extraction_confidence: float = 0.0
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    llm_provider: str | None = None
    llm_model: str | None = None
    timestamp: datetime | None = None


class CandidateProfile(_Model):
    """Structured candidate profile extracted from a resume."""

    personal_info: PersonalInfo = Field(default_factory=PersonalInfo)
    professional_summary: str | None = None
    education: list[EducationEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    skills: Skills = Field(default_factory=Skills)
    certifications: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    leadership: list[str] = Field(default_factory=list)
    publications: list[str] = Field(default_factory=list)
    open_source: list[str] = Field(default_factory=list)
    hackathons: list[str] = Field(default_factory=list)
    awards: list[str] = Field(default_factory=list)
    languages_known: list[str] = Field(default_factory=list)

    # Deduplicated, flattened technology list (engine-computed).
    technology_stack: list[str] = Field(default_factory=list)

    # Engine-computed extraction metadata.
    metadata: ExtractionMetadata = Field(default_factory=ExtractionMetadata)
