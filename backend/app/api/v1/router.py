"""Aggregates all v1 endpoint routers into a single APIRouter.

Mounted by the app under the configured `api_v1_prefix` (default `/api/v1`).
New feature routers (jobs, candidates, ranking, ...) are included here in
future sprints.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    candidates,
    decisions,
    dna,
    documents,
    explanations,
    health,
    hidden_skills,
    jobs,
    knowledge,
    meta,
    ranking,
    simulations,
    system,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(meta.router)
api_router.include_router(documents.router)
api_router.include_router(candidates.router)
api_router.include_router(jobs.router)
api_router.include_router(knowledge.router)
api_router.include_router(hidden_skills.router)
api_router.include_router(system.router)
api_router.include_router(dna.router)
api_router.include_router(decisions.router)
api_router.include_router(explanations.router)
api_router.include_router(simulations.router)
api_router.include_router(ranking.router)
