"""Hiring Simulator service.

Orchestrates "what-if" scenarios by:
  1. building a *modified* JobProfile from editable criteria,
  2. building a bounded, weight-overridden DecisionConfig,
  3. recomputing DecisionProfiles with the **existing** deterministic
     `DecisionIntelligenceEngine.compute()` (no LLM, no persistence),
  4. computing rank/score deltas vs the unmodified baseline,
  5. producing updated explanations via the **existing**
     `ExplainabilityEngine.build()`.

No engine logic is changed and no stored evaluation is overwritten.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.schema import CandidateProfile
from app.core.exceptions import NotFoundError, ValidationError
from app.decision import DecisionConfig, DecisionIntelligenceEngine
from app.decision.engine import COMPONENTS
from app.decision.model import DecisionProfile
from app.dna.model import CandidateDNA
from app.explainability import ExplainabilityEngine
from app.hidden_skills.model import HiddenSkillProfile
from app.jobs.schema import JobProfile
from app.models.candidate import CandidateProfileRecord
from app.repositories.candidate import CandidateRepository
from app.repositories.dna import DNARepository
from app.repositories.hidden_skill import HiddenSkillRepository
from app.repositories.job import JobRepository
from app.schemas.simulation import (
    CandidateSimResult,
    ComponentDelta,
    SimulationRequest,
    SimulationResult,
)
from app.services.base import BaseService

_SIM_PROFILE = "__simulation__"
_MAX_WEIGHT = 1.0
_VALID_KEYS = {key for key, _ in COMPONENTS}
_REASON_THRESHOLD = 0.05


def _ci_remove(items: list[str], targets: list[str]) -> list[str]:
    lowered = {t.strip().lower() for t in targets}
    return [i for i in items if i.strip().lower() not in lowered]


def _ci_add(items: list[str], additions: list[str]) -> list[str]:
    existing = {i.strip().lower() for i in items}
    result = list(items)
    for a in additions:
        if a.strip() and a.strip().lower() not in existing:
            result.append(a.strip())
            existing.add(a.strip().lower())
    return result


class SimulationService(BaseService):
    """Runs interactive, non-persisting hiring simulations."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        decision_engine: DecisionIntelligenceEngine,
        explainability_engine: ExplainabilityEngine,
        candidate_repository: CandidateRepository | None = None,
        job_repository: JobRepository | None = None,
        hidden_skill_repository: HiddenSkillRepository | None = None,
        dna_repository: DNARepository | None = None,
    ) -> None:
        super().__init__(session)
        self.engine = decision_engine
        self.explain = explainability_engine
        self.candidates = candidate_repository or CandidateRepository(session)
        self.jobs = job_repository or JobRepository(session)
        self.hidden = hidden_skill_repository or HiddenSkillRepository(session)
        self.dna = dna_repository or DNARepository(session)

    async def run(self, req: SimulationRequest) -> SimulationResult:
        job_record = await self.jobs.get(req.job_id)
        if job_record is None:
            raise NotFoundError(f"Job {req.job_id} not found")
        original_job = JobProfile.model_validate(job_record.profile)
        modified_job = self._modify_job(original_job, req)

        bundles = await self._load_candidates(req.candidate_ids)
        if not bundles:
            raise ValidationError("No candidates available to simulate")

        # Baseline: original job, auto-selected weighting (deterministic compute).
        baselines: dict[str, DecisionProfile] = {
            cid: self.engine.compute(profile, original_job, hidden=hidden, dna=dna)
            for cid, (_, profile, hidden, dna) in bundles.items()
        }
        base_profile_name = self._resolve_base_profile(req, baselines)

        # Build the (optionally weight-overridden) simulation engine + profile.
        sim_engine, sim_profile = self._build_sim_engine(req, base_profile_name)

        modified: dict[str, DecisionProfile] = {
            cid: sim_engine.compute(
                profile, modified_job, hidden=hidden, dna=dna, weighting_profile=sim_profile
            )
            for cid, (_, profile, hidden, dna) in bundles.items()
        }

        baseline_rank = self._rank(baselines)
        new_rank = self._rank(modified)

        results: list[CandidateSimResult] = []
        for cid, (record, profile, _, _) in bundles.items():
            base = baselines[cid]
            new = modified[cid]
            deltas = self._component_deltas(base, new)
            explanation = self.explain.build(
                new,
                candidate=profile,
                job_title=modified_job.job_metadata.job_title,
                candidate_name=record.full_name,
            )
            results.append(
                CandidateSimResult(
                    candidate_id=cid,
                    candidate_name=record.full_name,
                    baseline_score=base.overall_match_score,
                    new_score=new.overall_match_score,
                    delta=round(new.overall_match_score - base.overall_match_score, 4),
                    baseline_rank=baseline_rank[cid],
                    new_rank=new_rank[cid],
                    rank_delta=baseline_rank[cid] - new_rank[cid],
                    baseline_recommendation=base.recommendation.value,
                    new_recommendation=new.recommendation.value,
                    component_deltas=deltas,
                    change_reasons=self._change_reasons(deltas),
                    explanation=explanation,
                )
            )

        results.sort(key=lambda r: r.new_rank)
        return SimulationResult(
            weighting_profile=next(iter(modified.values())).weighting_profile,
            applied_overrides=self._summarize(req),
            results=results,
        )

    # ── Job modification ────────────────────────────────────
    @staticmethod
    def _modify_job(job: JobProfile, req: SimulationRequest) -> JobProfile:
        j = job.model_copy(deep=True)
        required = list(j.required_skills)
        preferred = list(j.preferred_skills)

        # Move required <-> preferred.
        if req.move_to_preferred:
            required = _ci_remove(required, req.move_to_preferred)
            preferred = _ci_add(preferred, req.move_to_preferred)
        if req.move_to_required:
            preferred = _ci_remove(preferred, req.move_to_required)
            required = _ci_add(required, req.move_to_required)

        # Add / remove.
        required = _ci_add(required, req.add_required)
        preferred = _ci_add(preferred, req.add_preferred)
        if req.remove_skills:
            required = _ci_remove(required, req.remove_skills)
            preferred = _ci_remove(preferred, req.remove_skills)

        j.required_skills = required
        j.preferred_skills = preferred
        if req.min_experience is not None:
            j.experience.minimum_years = req.min_experience
        if req.education_required is not None:
            j.education.required = req.education_required
        return j

    # ── Weighting / engine selection ────────────────────────
    def _resolve_base_profile(
        self, req: SimulationRequest, baselines: dict[str, DecisionProfile]
    ) -> str:
        if req.role_profile and req.role_profile in self.engine.config.profiles:
            return req.role_profile
        # All candidates share the same job-derived profile; take the first.
        first = next(iter(baselines.values()))
        return first.weighting_profile

    def _build_sim_engine(
        self, req: SimulationRequest, base_profile_name: str
    ) -> tuple[DecisionIntelligenceEngine, str | None]:
        if req.weight_overrides:
            base_config = self.engine.config
            weights = dict(base_config.profiles.get(base_profile_name, {}))
            for key, value in req.weight_overrides.items():
                if key in _VALID_KEYS:
                    weights[key] = max(0.0, min(_MAX_WEIGHT, float(value)))
            sim_config = DecisionConfig(
                profiles={**base_config.profiles, _SIM_PROFILE: weights},
                thresholds=base_config.thresholds,
                role_keywords=base_config.role_keywords,
                semantic_partial_credit=base_config.semantic_partial_credit,
            )
            sim_engine = DecisionIntelligenceEngine(
                self.engine.graph, self.engine.llm, self.engine.prompts, config=sim_config
            )
            return sim_engine, _SIM_PROFILE

        # No weight overrides: reuse the existing engine; pick role profile if valid.
        profile = (
            req.role_profile
            if req.role_profile and req.role_profile in self.engine.config.profiles
            else None
        )
        return self.engine, profile

    # ── Deltas / ranking ────────────────────────────────────
    @staticmethod
    def _rank(decisions: dict[str, DecisionProfile]) -> dict[str, int]:
        ordered = sorted(
            decisions.items(),
            key=lambda kv: (-kv[1].overall_match_score, kv[0]),
        )
        return {cid: i + 1 for i, (cid, _) in enumerate(ordered)}

    @staticmethod
    def _component_deltas(base: DecisionProfile, new: DecisionProfile) -> list[ComponentDelta]:
        base_by_key = {c.key: c for c in base.components}
        deltas: list[ComponentDelta] = []
        for c in new.components:
            b = base_by_key.get(c.key)
            base_score = b.score if b else 0.0
            deltas.append(
                ComponentDelta(
                    key=c.key,
                    name=c.name,
                    baseline=base_score,
                    new=c.score,
                    delta=round(c.score - base_score, 4),
                )
            )
        return deltas

    @staticmethod
    def _change_reasons(deltas: list[ComponentDelta]) -> list[str]:
        movers = sorted(deltas, key=lambda d: abs(d.delta), reverse=True)
        reasons = [
            f"{d.name} {'improved' if d.delta > 0 else 'dropped'} ({d.delta:+.2f})"
            for d in movers
            if abs(d.delta) >= _REASON_THRESHOLD
        ]
        return reasons[:3] or ["No component-level change."]

    @staticmethod
    def _summarize(req: SimulationRequest) -> dict[str, object]:
        summary: dict[str, object] = {}
        if req.role_profile:
            summary["role_profile"] = req.role_profile
        if req.move_to_required:
            summary["moved_to_required"] = req.move_to_required
        if req.move_to_preferred:
            summary["moved_to_preferred"] = req.move_to_preferred
        if req.add_required:
            summary["added_required"] = req.add_required
        if req.add_preferred:
            summary["added_preferred"] = req.add_preferred
        if req.remove_skills:
            summary["removed_skills"] = req.remove_skills
        if req.min_experience is not None:
            summary["min_experience"] = req.min_experience
        if req.education_required is not None:
            summary["education_required"] = req.education_required
        if req.weight_overrides:
            summary["weight_overrides"] = req.weight_overrides
        return summary

    # ── Loading ─────────────────────────────────────────────
    async def _load_candidates(self, candidate_ids: list[uuid.UUID] | None) -> dict[
        str,
        tuple[
            CandidateProfileRecord, CandidateProfile, HiddenSkillProfile | None, CandidateDNA | None
        ],
    ]:
        if candidate_ids is None:
            records = await self.candidates.list(limit=200)
        else:
            records = []
            for cid in candidate_ids:
                rec = await self.candidates.get(cid)
                if rec is not None:
                    records.append(rec)

        bundles: dict[
            str,
            tuple[
                CandidateProfileRecord,
                CandidateProfile,
                HiddenSkillProfile | None,
                CandidateDNA | None,
            ],
        ] = {}
        for rec in records:
            profile = CandidateProfile.model_validate(rec.profile)
            hrec = await self.hidden.get_latest_for_candidate(rec.id)
            hidden = HiddenSkillProfile.model_validate(hrec.profile) if hrec else None
            drec = await self.dna.get_latest_for_candidate(rec.id)
            dna = CandidateDNA.model_validate(drec.dna) if drec else None
            bundles[str(rec.id)] = (rec, profile, hidden, dna)
        return bundles
