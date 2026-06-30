"""Health endpoint (versioned mirror).

A versioned health probe under `/api/v1/health` in addition to the root
`/health` used by container orchestration.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import SettingsDep
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Health probe (v1)")
async def health(settings: SettingsDep) -> HealthResponse:
    """Return service liveness and active environment."""
    return HealthResponse(status="ok", environment=settings.app_env.value)
