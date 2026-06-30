"""Sprint 9.1 ranking schemas.

Defines the *input* contract for the official Redrob dataset and the *output*
contract for the offline ranking engine. The Redrob candidate already arrives
structured, so it is loaded directly (NO Candidate Intelligence extraction) and
mapped onto the existing canonical `CandidateProfile` used by every downstream
engine. Behavioral signals are kept separate (they are not part of a resume).

All input models use `extra="ignore"` and default-everything so a 100k-row,
real-world JSONL never fails to load on an unexpected/missing field.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

# Deterministic reference date for converting absolute dataset dates (e.g.
# ``last_active_date``) into "days ago". Fixed (not ``datetime.now()``) so a
# ranking run is fully reproducible regardless of wall-clock time. Matches the
# dataset snapshot window (signals dated up to mid-2026).
_REFERENCE_DATE = date(2026, 6, 30)


class _In(BaseModel):
    """Lenient input base (ignore unknown keys; accept field name or alias)."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


def _days_since(value: Any) -> float | None:
    """Whole days from an ISO ``YYYY-MM-DD`` date to the reference date."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        d = date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None
    return float((_REFERENCE_DATE - d).days)


# ── Redrob candidate input ──────────────────────────────────
class RedrobProfile(_In):
    # Official dataset uses ``anonymized_name``; accept either.
    full_name: str | None = Field(
        default=None, validation_alias=AliasChoices("full_name", "anonymized_name")
    )
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    headline: str | None = None
    summary: str | None = None


class RedrobCareerEntry(_In):
    company: str | None = None
    title: str | None = None
    role: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration: str | None = None
    duration_months: int | None = None
    description: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)

    @field_validator("responsibilities", "technologies", mode="before")
    @classmethod
    def _coerce_list(cls, v: Any) -> list[str]:
        return _as_str_list(v)


class RedrobEducationEntry(_In):
    institution: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    grade: str | None = None


class RedrobSignals(_In):
    """Behavioral / engagement signals attached to a Redrob candidate.

    Every field is optional; the Behavioral Intelligence Engine degrades
    gracefully and records what evidence was available.
    """

    # Availability
    open_to_work: bool = False
    notice_period_days: float | None = None
    last_active_days: float | None = None
    response_time_hours: float | None = None
    # Responsiveness
    recruiter_response_rate: float | None = None
    avg_response_time_hours: float | None = None
    interview_completion_rate: float | None = None
    # Recruiter interest
    profile_views: float | None = None
    saved_by_recruiters: float | None = None
    search_appearances: float | None = None
    # Credibility
    verified_email: bool = False
    verified_phone: bool = False
    profile_completeness: float | None = None
    linkedin_connected: bool = False
    # Technical activity
    github_activity_score: float | None = None
    skill_assessment_scores: list[float] = Field(default_factory=list)
    # Learning
    recent_activity_days: float | None = None
    assessment_participation: float | None = None
    # Compensation
    expected_salary: float | None = None
    relocation: bool = False
    preferred_work_mode: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _adapt_official(cls, data: Any) -> Any:
        """Map official Redrob ``redrob_signals`` keys onto internal fields.

        This is a pure input adapter — it only renames/normalizes already-present
        signal values (no scoring logic). Internal field names are still accepted
        (so unit tests and other callers keep working). Unmapped official keys
        are dropped by ``extra="ignore"``.
        """
        if not isinstance(data, dict):
            return data
        d = dict(data)

        def carry(src: str, dst: str) -> None:
            if src in d and dst not in d:
                d[dst] = d[src]

        carry("open_to_work_flag", "open_to_work")
        carry("willing_to_relocate", "relocation")
        carry("profile_views_received_30d", "profile_views")
        carry("search_appearance_30d", "search_appearances")
        carry("saved_by_recruiters_30d", "saved_by_recruiters")
        # profile_completeness_score is 0-100; the engine's _rate() normalizes it.
        carry("profile_completeness_score", "profile_completeness")

        # Absolute activity date -> "days ago" (deterministic reference date).
        days = _days_since(d.get("last_active_date"))
        if days is not None:
            d.setdefault("last_active_days", days)
            d.setdefault("recent_activity_days", days)

        # skill_assessment_scores is an object {skill: score}; participation =
        # number of completed assessments. (The field validator below converts
        # the object's values into the normalized score list.)
        sa = d.get("skill_assessment_scores")
        if isinstance(sa, dict):
            d.setdefault("assessment_participation", float(len(sa)))

        # expected_salary_range_inr_lpa {min,max} -> midpoint.
        rng = d.get("expected_salary_range_inr_lpa")
        if isinstance(rng, dict):
            vals = [v for v in (rng.get("min"), rng.get("max")) if isinstance(v, int | float)]
            if vals:
                d.setdefault("expected_salary", sum(vals) / len(vals))

        return d

    @field_validator("skill_assessment_scores", mode="before")
    @classmethod
    def _coerce_scores(cls, v: Any) -> list[float]:
        if v is None:
            return []
        if isinstance(v, dict):
            v = list(v.values())
        if not isinstance(v, list):
            v = [v]
        out: list[float] = []
        for item in v:
            try:
                out.append(float(item))
            except (TypeError, ValueError):
                continue
        return out


class RedrobCandidate(_In):
    """One structured candidate row from the official Redrob dataset."""

    candidate_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    profile: RedrobProfile = Field(default_factory=RedrobProfile)
    career_history: list[RedrobCareerEntry] = Field(default_factory=list)
    education: list[RedrobEducationEntry] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    redrob_signals: RedrobSignals = Field(default_factory=RedrobSignals)

    @field_validator("candidate_id", mode="before")
    @classmethod
    def _coerce_id(cls, v: Any) -> str:
        if v is None:
            return str(uuid.uuid4())
        return str(v)

    @field_validator("skills", "certifications", "languages", mode="before")
    @classmethod
    def _coerce_list(cls, v: Any) -> list[str]:
        return _as_str_list(v)


def _as_str_list(value: Any) -> list[str]:
    """Coerce heterogeneous dataset values into a clean list[str].

    Accepts a list of strings, a list of objects (extracts ``name``/``skill``/
    ``title``), a single string, or ``None``.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        value = list(value.values())
    if not isinstance(value, list):
        return [str(value)]
    out: list[str] = []
    for item in value:
        if item is None:
            continue
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            raw = item.get("name") or item.get("skill") or item.get("title") or item.get("value")
            text = str(raw).strip() if raw is not None else ""
        else:
            text = str(item).strip()
        if text:
            out.append(text)
    return out


# ── Behavioral engine output ────────────────────────────────
class BehavioralSignalScore(BaseModel):
    """One normalized (0..1) behavioral sub-score with its evidence."""

    key: str
    name: str
    score: float
    confidence: float
    evidence: list[str] = Field(default_factory=list)
    reasoning: str = ""


class BehavioralProfile(BaseModel):
    """Deterministic behavioral fingerprint (no LLM, fully explainable).

    Structurally implements `app.decision.engine.BehavioralMatchLike`, so it can
    be passed straight into the Decision Engine's optional Behavioral Match
    component without any import coupling.
    """

    overall_score: float
    confidence: float = 0.0
    components: list[BehavioralSignalScore] = Field(default_factory=list)
    summary: str = ""

    @property
    def top_signals(self) -> list[str]:
        """Names of the strongest behavioral signals (score desc)."""
        return [c.name for c in sorted(self.components, key=lambda c: -c.score) if c.score >= 0.6]


# ── Job context for compensation compatibility ──────────────
class JobBehavioralContext(BaseModel):
    """Minimal job facts the behavioral engine needs (compensation only)."""

    salary_min: float | None = None
    salary_max: float | None = None
    work_mode: str | None = None


# ── Ranking I/O ─────────────────────────────────────────────
class RankingRequest(BaseModel):
    """Request to run an offline batch ranking over the Redrob dataset."""

    job_id: uuid.UUID
    dataset_path: str | None = None  # defaults to configured dataset path
    top_n: int | None = None  # defaults to ranking_config.json
    role_profile: str | None = None
    export_csv: bool = False
    csv_path: str | None = None


class RankedCandidate(BaseModel):
    """One ranked candidate in the result (compact, evidence-backed)."""

    candidate_id: str
    rank: int
    score: float
    recommendation: str
    candidate_name: str | None = None
    behavioral_score: float
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    top_behavioral_signals: list[str] = Field(default_factory=list)
    reasoning: str


class RankingResult(BaseModel):
    """Outcome of an offline ranking run."""

    job_id: uuid.UUID
    job_title: str | None
    weighting_profile: str
    total_candidates: int
    returned: int
    top: list[RankedCandidate]
    csv_path: str | None = None
    elapsed_seconds: float
