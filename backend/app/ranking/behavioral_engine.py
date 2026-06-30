"""Behavioral Intelligence Engine (Sprint 9.1).

Deterministic, fully explainable scoring of a candidate's Redrob engagement
signals. NO LLM. NO APIs. Every sub-score is normalized to 0..1 and every
weight / threshold comes from an external JSON config (`behavior_weights.json`)
— there are no magic constants in this module.

The engine produces seven normalized signals (Availability, Responsiveness,
Recruiter Interest, Credibility, Technical Activity, Learning, Compensation
Compatibility) and a single weighted `overall_score`. The overall score feeds
the Decision Engine's new, optional "Behavioral Match" component.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.ranking.schemas import (
    BehavioralProfile,
    BehavioralSignalScore,
    JobBehavioralContext,
    RedrobSignals,
)

_DATA_DIR = Path(__file__).parent / "data"
_DEFAULT_WEIGHTS = _DATA_DIR / "behavior_weights.json"

_WORK_MODES = {"remote", "hybrid", "onsite"}


@dataclass
class BehavioralConfig:
    """Externalized weights + normalization parameters."""

    component_weights: dict[str, float]
    params: dict[str, dict[str, Any]]


def load_behavior_weights(path: str | Path = _DEFAULT_WEIGHTS) -> BehavioralConfig:
    """Load behavioral weights + normalization params from JSON."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    component_weights = {k: float(v) for k, v in data["component_weights"].items()}
    params = {k: v for k, v in data.items() if k != "component_weights"}
    return BehavioralConfig(component_weights=component_weights, params=params)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _rate(value: float | None) -> float | None:
    """Normalize a rate that may be expressed as 0..1 or 0..100."""
    if value is None:
        return None
    return _clamp01(value / 100.0 if value > 1.0 else value)


def _decay_days(days: float | None, max_days: float) -> float | None:
    """1.0 for very recent / short, decaying linearly to 0 at ``max_days``."""
    if days is None or max_days <= 0:
        return None
    return _clamp01(1.0 - days / max_days)


class BehavioralIntelligenceEngine:
    """Deterministic behavioral signal scorer."""

    def __init__(self, *, config: BehavioralConfig) -> None:
        self.config = config

    # ── Public API ──────────────────────────────────────────
    def compute(
        self,
        signals: RedrobSignals,
        *,
        job: JobBehavioralContext | None = None,
    ) -> BehavioralProfile:
        """Compute all behavioral sub-scores and the weighted overall score."""
        components = [
            self._availability(signals),
            self._responsiveness(signals),
            self._recruiter_interest(signals),
            self._credibility(signals),
            self._technical_activity(signals),
            self._learning_signal(signals),
            self._compensation_compatibility(signals, job),
        ]
        weights = self.config.component_weights
        total_w = sum(weights.get(c.key, 0.0) for c in components) or 1.0
        overall = round(sum(weights.get(c.key, 0.0) * c.score for c in components) / total_w, 4)
        confidence = round(
            sum(weights.get(c.key, 0.0) * c.confidence for c in components) / total_w, 4
        )
        strongest = max(components, key=lambda c: c.score)
        summary = (
            f"Behavioral score {overall:.2f}; strongest signal: "
            f"{strongest.name} ({strongest.score:.2f})."
        )
        return BehavioralProfile(
            overall_score=overall,
            confidence=confidence,
            components=components,
            summary=summary,
        )

    # ── Signal computations ─────────────────────────────────
    def _availability(self, s: RedrobSignals) -> BehavioralSignalScore:
        cfg = self.config.params["availability"]
        sub = cfg["sub_weights"]
        parts: dict[str, float] = {}
        evidence: list[str] = []

        parts["open_to_work"] = 1.0 if s.open_to_work else 0.0
        evidence.append(f"open_to_work={s.open_to_work}")

        notice = _decay_days(s.notice_period_days, float(cfg["max_notice_period_days"]))
        if notice is not None:
            parts["notice_period"] = notice
            evidence.append(f"notice_period={s.notice_period_days:g}d")
        active = _decay_days(s.last_active_days, float(cfg["max_inactive_days"]))
        if active is not None:
            parts["last_active"] = active
            evidence.append(f"last_active={s.last_active_days:g}d ago")
        resp = _decay_days(s.response_time_hours, float(cfg["max_response_hours"]))
        if resp is not None:
            parts["response_time"] = resp
            evidence.append(f"response_time={s.response_time_hours:g}h")

        return self._blend("availability", "Availability Score", sub, parts, evidence)

    def _responsiveness(self, s: RedrobSignals) -> BehavioralSignalScore:
        cfg = self.config.params["responsiveness"]
        sub = cfg["sub_weights"]
        parts: dict[str, float] = {}
        evidence: list[str] = []

        rrr = _rate(s.recruiter_response_rate)
        if rrr is not None:
            parts["recruiter_response_rate"] = rrr
            evidence.append(f"recruiter_response_rate={rrr:.2f}")
        art = _decay_days(s.avg_response_time_hours, float(cfg["max_response_hours"]))
        if art is not None:
            parts["avg_response_time"] = art
            evidence.append(f"avg_response_time={s.avg_response_time_hours:g}h")
        icr = _rate(s.interview_completion_rate)
        if icr is not None:
            parts["interview_completion_rate"] = icr
            evidence.append(f"interview_completion_rate={icr:.2f}")

        return self._blend("responsiveness", "Responsiveness Score", sub, parts, evidence)

    def _recruiter_interest(self, s: RedrobSignals) -> BehavioralSignalScore:
        cfg = self.config.params["recruiter_interest"]
        sub = cfg["sub_weights"]
        parts: dict[str, float] = {}
        evidence: list[str] = []

        if s.profile_views is not None:
            parts["profile_views"] = _clamp01(
                s.profile_views / float(cfg["profile_views_saturation"])
            )
            evidence.append(f"profile_views={s.profile_views:g}")
        if s.saved_by_recruiters is not None:
            parts["saved_by_recruiters"] = _clamp01(
                s.saved_by_recruiters / float(cfg["saved_by_recruiters_saturation"])
            )
            evidence.append(f"saved_by_recruiters={s.saved_by_recruiters:g}")
        if s.search_appearances is not None:
            parts["search_appearances"] = _clamp01(
                s.search_appearances / float(cfg["search_appearances_saturation"])
            )
            evidence.append(f"search_appearances={s.search_appearances:g}")

        return self._blend("recruiter_interest", "Recruiter Interest Score", sub, parts, evidence)

    def _credibility(self, s: RedrobSignals) -> BehavioralSignalScore:
        cfg = self.config.params["credibility"]
        sub = cfg["sub_weights"]
        parts: dict[str, float] = {
            "verified_email": 1.0 if s.verified_email else 0.0,
            "verified_phone": 1.0 if s.verified_phone else 0.0,
            "linkedin_connected": 1.0 if s.linkedin_connected else 0.0,
        }
        evidence = [
            f"verified_email={s.verified_email}",
            f"verified_phone={s.verified_phone}",
            f"linkedin_connected={s.linkedin_connected}",
        ]
        completeness = _rate(s.profile_completeness)
        if completeness is not None:
            parts["profile_completeness"] = completeness
            evidence.append(f"profile_completeness={completeness:.2f}")

        return self._blend("credibility", "Credibility Score", sub, parts, evidence)

    def _technical_activity(self, s: RedrobSignals) -> BehavioralSignalScore:
        cfg = self.config.params["technical_activity"]
        sub = cfg["sub_weights"]
        parts: dict[str, float] = {}
        evidence: list[str] = []

        if s.github_activity_score is not None:
            parts["github_activity"] = _clamp01(
                s.github_activity_score / float(cfg["github_activity_max"])
            )
            evidence.append(f"github_activity={s.github_activity_score:g}")
        if s.skill_assessment_scores:
            avg = sum(s.skill_assessment_scores) / len(s.skill_assessment_scores)
            parts["skill_assessments"] = _clamp01(avg / float(cfg["skill_assessment_max"]))
            evidence.append(f"skill_assessments_avg={avg:g} (n={len(s.skill_assessment_scores)})")

        return self._blend("technical_activity", "Technical Activity Score", sub, parts, evidence)

    def _learning_signal(self, s: RedrobSignals) -> BehavioralSignalScore:
        cfg = self.config.params["learning_signal"]
        sub = cfg["sub_weights"]
        parts: dict[str, float] = {}
        evidence: list[str] = []

        recent = _decay_days(s.recent_activity_days, float(cfg["max_inactive_days"]))
        if recent is not None:
            parts["recent_activity"] = recent
            evidence.append(f"recent_activity={s.recent_activity_days:g}d ago")
        if s.assessment_participation is not None:
            value = s.assessment_participation
            normalized = (
                _clamp01(value)
                if value <= 1.0
                else _clamp01(value / float(cfg["assessment_participation_saturation"]))
            )
            parts["assessment_participation"] = normalized
            evidence.append(f"assessment_participation={value:g}")
        completeness = _rate(s.profile_completeness)
        if completeness is not None:
            parts["profile_completeness"] = completeness
            evidence.append(f"profile_completeness={completeness:.2f}")

        return self._blend("learning_signal", "Learning Signal", sub, parts, evidence)

    def _compensation_compatibility(
        self, s: RedrobSignals, job: JobBehavioralContext | None
    ) -> BehavioralSignalScore:
        cfg = self.config.params["compensation_compatibility"]
        sub = cfg["sub_weights"]
        neutral = float(cfg["neutral_score"])
        parts: dict[str, float] = {}
        evidence: list[str] = []

        # Salary fit (needs job context).
        salary_fit = self._salary_fit(s.expected_salary, job, cfg, neutral)
        if salary_fit is not None:
            parts["salary"] = salary_fit
            if s.expected_salary is not None:
                evidence.append(f"expected_salary={s.expected_salary:g}")

        parts["relocation"] = 1.0 if s.relocation else neutral
        evidence.append(f"relocation={s.relocation}")

        mode = (s.preferred_work_mode or "").strip().lower()
        if mode in _WORK_MODES and job is not None and job.work_mode:
            parts["work_mode"] = 1.0 if mode == job.work_mode.strip().lower() else 0.0
            evidence.append(f"work_mode={mode} vs job={job.work_mode}")
        elif mode in _WORK_MODES:
            parts["work_mode"] = neutral
            evidence.append(f"work_mode={mode} (no job work mode)")

        return self._blend(
            "compensation_compatibility",
            "Compensation Compatibility",
            sub,
            parts,
            evidence,
            default=neutral,
        )

    @staticmethod
    def _salary_fit(
        expected: float | None,
        job: JobBehavioralContext | None,
        cfg: dict[str, Any],
        neutral: float,
    ) -> float | None:
        if expected is None:
            return None
        if job is None or (job.salary_min is None and job.salary_max is None):
            return neutral  # signal present but no job band to compare against
        lo = job.salary_min if job.salary_min is not None else 0.0
        hi = job.salary_max if job.salary_max is not None else lo
        if hi <= 0:
            return neutral
        if expected <= hi:
            return 1.0
        # Above band: decay across the configured overshoot tolerance.
        tolerance = float(cfg["salary_overshoot_tolerance"]) * hi
        if tolerance <= 0:
            return 0.0
        return _clamp01(1.0 - (expected - hi) / tolerance)

    # ── Blending ────────────────────────────────────────────
    @staticmethod
    def _blend(
        key: str,
        name: str,
        sub_weights: dict[str, Any],
        parts: dict[str, float],
        evidence: list[str],
        *,
        default: float = 0.0,
    ) -> BehavioralSignalScore:
        """Weighted blend over the sub-signals that were actually present.

        Confidence reflects how much of the signal's evidence was available
        (sum of present sub-weights / total sub-weights).
        """
        total = sum(float(sub_weights.get(k, 0.0)) for k in sub_weights)
        present = sum(float(sub_weights.get(k, 0.0)) for k in parts)
        if present <= 0:
            return BehavioralSignalScore(
                key=key,
                name=name,
                score=round(default, 4),
                confidence=0.0,
                evidence=evidence or ["no signals available"],
                reasoning=f"No {name.lower()} signals available; using default {default:.2f}.",
            )
        score = sum(float(sub_weights.get(k, 0.0)) * v for k, v in parts.items()) / present
        confidence = round(present / total, 4) if total > 0 else 0.0
        return BehavioralSignalScore(
            key=key,
            name=name,
            score=round(_clamp01(score), 4),
            confidence=confidence,
            evidence=evidence,
            reasoning=f"{name} from {len(parts)} signal(s); coverage {confidence:.0%}.",
        )
