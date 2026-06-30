"""Hiring Simulator endpoint.

POST /simulations/run   recompute rankings for a what-if scenario (no persistence).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import SimulationServiceDep
from app.schemas.simulation import SimulationRequest, SimulationResult

router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.post("/run", response_model=SimulationResult, summary="Run a what-if hiring simulation")
async def run_simulation(
    payload: SimulationRequest, service: SimulationServiceDep
) -> SimulationResult:
    return await service.run(payload)
