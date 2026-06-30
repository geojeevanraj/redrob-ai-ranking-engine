"""Hidden Skill Inference data model.

`HiddenSkillProfile` is the output of the engine: a set of skills that are NOT
explicitly listed on a candidate but are strongly supported by evidence in the
Knowledge Graph. Every inferred skill carries its full, traceable evidence
chain — the engine never hallucinates.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceStep(BaseModel):
    """One hop in an evidence path: source --relationship--> target."""

    source: str
    relationship: str
    target: str


class EvidencePath(BaseModel):
    """A path from an explicit (origin) skill to an inferred skill."""

    origin_skill: str  # node id of the explicit skill that seeded this path
    steps: list[EvidenceStep] = Field(default_factory=list)


class HiddenSkill(BaseModel):
    """A single inferred skill with its evidence and verification status."""

    model_config = ConfigDict(extra="ignore")

    inferred_skill: str  # display name
    skill_id: str  # knowledge-graph node id
    confidence: float
    evidence_nodes: list[str] = Field(default_factory=list)
    evidence_paths: list[EvidencePath] = Field(default_factory=list)
    reasoning_summary: str = ""
    verified_by_llm: bool = False


class HiddenSkillProfile(BaseModel):
    """The full set of evidence-backed hidden skills for a candidate."""

    model_config = ConfigDict(extra="ignore")

    skills: list[HiddenSkill] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    timestamp: datetime | None = None
    thresholds: dict[str, Any] = Field(default_factory=dict)
