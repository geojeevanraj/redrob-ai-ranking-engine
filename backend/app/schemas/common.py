"""Shared API response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response for the health probe."""

    status: str = Field(examples=["ok"])
    environment: str = Field(examples=["development"])


class VersionResponse(BaseModel):
    """Response describing the running service version."""

    name: str
    version: str
    api_version: str = Field(examples=["v1"])


class RootResponse(BaseModel):
    """Friendly root response with helpful links."""

    message: str
    docs_url: str
    health_url: str
