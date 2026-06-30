"""Meta endpoints: version information.

Part of the versioned API (`/api/v1/version`). The unversioned `GET /health`
and `GET /` live at the app root (see app.main).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import SettingsDep
from app.schemas import VersionResponse

router = APIRouter(tags=["meta"])


@router.get("/version", response_model=VersionResponse, summary="Service version")
async def version(settings: SettingsDep) -> VersionResponse:
    """Return service name, semantic version, and API version."""
    return VersionResponse(
        name=settings.app_name,
        version=settings.app_version,
        api_version="v1",
    )
