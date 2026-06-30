"""Common dependency-injection providers.

Typed `Annotated` aliases keep endpoint signatures clean and make the DI graph
explicit. Add repository/service providers here as they are introduced.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any, cast

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates import CandidateIntelligenceEngine
from app.candidates.engine import LLMManagerLike, PromptManagerLike
from app.config import Settings, get_settings
from app.db import get_session
from app.decision import DecisionConfig, DecisionIntelligenceEngine, load_decision_config
from app.dna import CandidateDNAEngine, DNAConfig, load_archetypes
from app.documents import DocumentIntelligenceEngine
from app.documents.storage import FileStorage, LocalFileStorage
from app.explainability import ExplainabilityEngine
from app.hidden_skills import HiddenSkillConfig, HiddenSkillInferenceEngine
from app.jobs import JobIntelligenceEngine
from app.knowledge import KnowledgeGraph, load_seed_graph
from app.ranking import (
    BehavioralIntelligenceEngine,
    RankingConfig,
    RankingService,
    load_behavior_weights,
    load_ranking_config,
)
from app.services.candidate_service import CandidateService
from app.services.decision_service import DecisionService
from app.services.dna_service import DNAService
from app.services.document_service import DocumentService
from app.services.explanation_service import ExplanationService
from app.services.hidden_skill_service import HiddenSkillService
from app.services.job_service import JobService
from app.services.simulation_service import SimulationService

# Async DB session, scoped per request.
DBSession = Annotated[AsyncSession, Depends(get_session)]

# Application settings (cached singleton).
SettingsDep = Annotated[Settings, Depends(get_settings)]


@lru_cache
def get_document_engine() -> DocumentIntelligenceEngine:
    """Process-wide, stateless document intelligence engine."""
    return DocumentIntelligenceEngine()


def get_file_storage(settings: SettingsDep) -> FileStorage:
    """Provide the configured file storage backend."""
    return LocalFileStorage(settings.document_storage_dir)


def get_document_service(
    session: DBSession,
    settings: SettingsDep,
    storage: Annotated[FileStorage, Depends(get_file_storage)],
    engine: Annotated[DocumentIntelligenceEngine, Depends(get_document_engine)],
) -> DocumentService:
    """Build a request-scoped `DocumentService`."""
    return DocumentService(
        session,
        storage=storage,
        engine=engine,
        allowed_extensions=settings.allowed_extensions_list,
        max_size_bytes=settings.max_upload_size_bytes,
    )


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]


# ── Candidate Intelligence wiring ───────────────────────────
@lru_cache
def get_llm_manager() -> LLMManagerLike:
    """Build the shared LLM Manager from configuration (cached).

    Imported lazily from the sibling `ai` package so the backend depends on it
    only at call time.
    """
    from ai.llm.manager import LLMManager

    return cast(LLMManagerLike, LLMManager.from_settings())


@lru_cache
def get_prompt_manager() -> PromptManagerLike:
    """Provide the shared Prompt Manager (cached)."""
    from ai.prompts import PromptManager

    return cast(PromptManagerLike, PromptManager())


def get_candidate_engine(
    llm: Annotated[LLMManagerLike, Depends(get_llm_manager)],
    prompts: Annotated[PromptManagerLike, Depends(get_prompt_manager)],
) -> CandidateIntelligenceEngine:
    """Build the Candidate Intelligence Engine."""
    return CandidateIntelligenceEngine(llm, prompts)


def get_candidate_service(
    session: DBSession,
    engine: Annotated[CandidateIntelligenceEngine, Depends(get_candidate_engine)],
) -> CandidateService:
    """Build a request-scoped `CandidateService`."""
    return CandidateService(session, engine=engine)


CandidateServiceDep = Annotated[CandidateService, Depends(get_candidate_service)]


# ── Job Intelligence wiring ─────────────────────────────────
def get_job_engine(
    llm: Annotated[LLMManagerLike, Depends(get_llm_manager)],
    prompts: Annotated[PromptManagerLike, Depends(get_prompt_manager)],
) -> JobIntelligenceEngine:
    """Build the Job Intelligence Engine."""
    return JobIntelligenceEngine(llm, prompts)


def get_job_service(
    session: DBSession,
    engine: Annotated[JobIntelligenceEngine, Depends(get_job_engine)],
) -> JobService:
    """Build a request-scoped `JobService`."""
    return JobService(session, engine=engine)


JobServiceDep = Annotated[JobService, Depends(get_job_service)]


# ── Knowledge Graph wiring ──────────────────────────────────
@lru_cache
def get_knowledge_graph() -> KnowledgeGraph:
    """Load the seed knowledge graph once per process (cached)."""
    return load_seed_graph()


# ── Hidden Skill Inference wiring ───────────────────────────
def get_hidden_skill_engine(
    settings: SettingsDep,
    llm: Annotated[LLMManagerLike, Depends(get_llm_manager)],
    prompts: Annotated[PromptManagerLike, Depends(get_prompt_manager)],
    graph: Annotated[KnowledgeGraph, Depends(get_knowledge_graph)],
) -> HiddenSkillInferenceEngine:
    """Build the Hidden Skill Inference Engine with configured thresholds."""
    config = HiddenSkillConfig(
        min_confidence=settings.hidden_skill_min_confidence,
        max_depth=settings.hidden_skill_max_depth,
        decay=settings.hidden_skill_decay,
        min_sources=settings.hidden_skill_min_sources,
        strong_single_threshold=settings.hidden_skill_strong_single_threshold,
    )
    return HiddenSkillInferenceEngine(graph, llm, prompts, config=config)


def get_hidden_skill_service(
    session: DBSession,
    engine: Annotated[HiddenSkillInferenceEngine, Depends(get_hidden_skill_engine)],
) -> HiddenSkillService:
    """Build a request-scoped `HiddenSkillService`."""
    return HiddenSkillService(session, engine=engine)


HiddenSkillServiceDep = Annotated[HiddenSkillService, Depends(get_hidden_skill_service)]


# ── Candidate DNA wiring ────────────────────────────────────
@lru_cache
def _load_dna_archetypes() -> tuple[Any, ...]:
    return tuple(load_archetypes())


def get_dna_engine(
    settings: SettingsDep,
    llm: Annotated[LLMManagerLike, Depends(get_llm_manager)],
    prompts: Annotated[PromptManagerLike, Depends(get_prompt_manager)],
    graph: Annotated[KnowledgeGraph, Depends(get_knowledge_graph)],
) -> CandidateDNAEngine:
    """Build the Candidate DNA Engine with configured thresholds + archetypes."""
    config = DNAConfig(
        archetypes=list(_load_dna_archetypes()),
        top_threshold=settings.dna_top_threshold,
        emerging_threshold=settings.dna_emerging_threshold,
        confidence_items=settings.dna_confidence_items,
        default_saturation=settings.dna_default_saturation,
    )
    return CandidateDNAEngine(graph, llm, prompts, config=config)


def get_dna_service(
    session: DBSession,
    engine: Annotated[CandidateDNAEngine, Depends(get_dna_engine)],
) -> DNAService:
    """Build a request-scoped `DNAService`."""
    return DNAService(session, engine=engine)


DNAServiceDep = Annotated[DNAService, Depends(get_dna_service)]


# ── Decision Intelligence wiring ────────────────────────────
@lru_cache
def _load_decision_config() -> DecisionConfig:
    return load_decision_config()


def get_decision_engine(
    llm: Annotated[LLMManagerLike, Depends(get_llm_manager)],
    prompts: Annotated[PromptManagerLike, Depends(get_prompt_manager)],
    graph: Annotated[KnowledgeGraph, Depends(get_knowledge_graph)],
) -> DecisionIntelligenceEngine:
    """Build the Decision Intelligence Engine with external weight config."""
    return DecisionIntelligenceEngine(graph, llm, prompts, config=_load_decision_config())


def get_decision_service(
    session: DBSession,
    engine: Annotated[DecisionIntelligenceEngine, Depends(get_decision_engine)],
) -> DecisionService:
    """Build a request-scoped `DecisionService`."""
    return DecisionService(session, engine=engine)


DecisionServiceDep = Annotated[DecisionService, Depends(get_decision_service)]


# ── Explainability wiring ───────────────────────────────────
def get_explainability_engine(
    llm: Annotated[LLMManagerLike, Depends(get_llm_manager)],
    prompts: Annotated[PromptManagerLike, Depends(get_prompt_manager)],
    graph: Annotated[KnowledgeGraph, Depends(get_knowledge_graph)],
) -> ExplainabilityEngine:
    """Build the Explainability Engine."""
    return ExplainabilityEngine(graph, llm, prompts)


def get_explanation_service(
    session: DBSession,
    engine: Annotated[ExplainabilityEngine, Depends(get_explainability_engine)],
) -> ExplanationService:
    """Build a request-scoped `ExplanationService`."""
    return ExplanationService(session, engine=engine)


ExplanationServiceDep = Annotated[ExplanationService, Depends(get_explanation_service)]


# ── Hiring Simulator wiring ─────────────────────────────────
def get_simulation_service(
    session: DBSession,
    decision_engine: Annotated[DecisionIntelligenceEngine, Depends(get_decision_engine)],
    explainability_engine: Annotated[ExplainabilityEngine, Depends(get_explainability_engine)],
) -> SimulationService:
    """Build a request-scoped `SimulationService` (reuses existing engines)."""
    return SimulationService(
        session, decision_engine=decision_engine, explainability_engine=explainability_engine
    )


SimulationServiceDep = Annotated[SimulationService, Depends(get_simulation_service)]


# ── Offline Ranking wiring (Sprint 9.1) ─────────────────────
@lru_cache
def get_behavioral_engine() -> BehavioralIntelligenceEngine:
    """Process-wide deterministic Behavioral Intelligence Engine (cached)."""
    return BehavioralIntelligenceEngine(config=load_behavior_weights())


@lru_cache
def _load_ranking_config() -> RankingConfig:
    return load_ranking_config()


def get_ranking_service(
    session: DBSession,
    settings: SettingsDep,
    decision_engine: Annotated[DecisionIntelligenceEngine, Depends(get_decision_engine)],
    hidden_engine: Annotated[HiddenSkillInferenceEngine, Depends(get_hidden_skill_engine)],
    dna_engine: Annotated[CandidateDNAEngine, Depends(get_dna_engine)],
    behavioral_engine: Annotated[BehavioralIntelligenceEngine, Depends(get_behavioral_engine)],
) -> RankingService:
    """Build a request-scoped `RankingService` (reuses existing engines)."""
    return RankingService(
        session,
        decision_engine=decision_engine,
        hidden_engine=hidden_engine,
        dna_engine=dna_engine,
        behavioral_engine=behavioral_engine,
        ranking_config=_load_ranking_config(),
        default_dataset_path=settings.ranking_dataset_path,
        export_dir=settings.ranking_export_dir,
    )


RankingServiceDep = Annotated[RankingService, Depends(get_ranking_service)]
