"""System status endpoint (read-only observability for the dev dashboard).

Aggregates information that no single existing endpoint exposes: LLM provider
availability + active provider, knowledge-graph load state, database
connectivity, and the current (non-secret) configuration. This is additive and
read-only — it does not change any pipeline behavior.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, Protocol

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text

from app.dependencies import DBSession, SettingsDep, get_knowledge_graph, get_llm_manager
from app.knowledge import KnowledgeGraph

router = APIRouter(prefix="/system", tags=["system"])


class _ManagerHealthLike(Protocol):
    async def health(self) -> Any: ...


class ProviderStatus(BaseModel):
    available: bool
    model: str | None = None
    detail: str | None = None


class LLMStatus(BaseModel):
    primary_provider: str
    fallback_provider: str | None = None
    providers: dict[str, ProviderStatus] = {}
    error: str | None = None


class KnowledgeGraphStatus(BaseModel):
    loaded: bool
    node_count: int
    edge_count: int


class SystemStatus(BaseModel):
    app_name: str
    version: str
    environment: str
    llm: LLMStatus
    knowledge_graph: KnowledgeGraphStatus
    database_connected: bool
    config: dict[str, Any]


@router.get("/status", response_model=SystemStatus, summary="System status snapshot")
async def system_status(
    settings: SettingsDep,
    session: DBSession,
    manager: Annotated[_ManagerHealthLike, Depends(get_llm_manager)],
    graph: Annotated[KnowledgeGraph, Depends(get_knowledge_graph)],
) -> SystemStatus:
    from ai.config import get_ai_settings

    ai = get_ai_settings()
    llm = await _llm_status(ai, manager)

    stats = graph.stats()
    kg = KnowledgeGraphStatus(
        loaded=stats.node_count > 0,
        node_count=stats.node_count,
        edge_count=stats.edge_count,
    )

    database_connected = await _check_db(session)

    return SystemStatus(
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env.value,
        llm=llm,
        knowledge_graph=kg,
        database_connected=database_connected,
        config={
            "primary_llm_provider": ai.primary_llm_provider,
            "fallback_llm_provider": ai.fallback_llm_provider,
            "gemini_model": ai.gemini_model,
            "ollama_model": ai.ollama_model,
            "ollama_host": ai.ollama_host,
            "llm_timeout": ai.llm_timeout,
            "llm_max_retries": ai.llm_max_retries,
            "embedding_model": ai.embedding_model,
            "max_upload_size_mb": settings.max_upload_size_mb,
            "allowed_document_extensions": settings.allowed_extensions_list,
            "hidden_skill_min_confidence": settings.hidden_skill_min_confidence,
            "hidden_skill_max_depth": settings.hidden_skill_max_depth,
        },
    )


async def _llm_status(ai: Any, manager: _ManagerHealthLike) -> LLMStatus:
    try:
        health = await asyncio.wait_for(manager.health(), timeout=5.0)
    except Exception as exc:
        return LLMStatus(
            primary_provider=ai.primary_llm_provider,
            fallback_provider=ai.fallback_llm_provider,
            error=f"health check unavailable: {exc}",
        )
    providers = {
        name: ProviderStatus(available=h.available, model=h.model, detail=h.detail)
        for name, h in health.providers.items()
    }
    return LLMStatus(
        primary_provider=health.primary_provider,
        fallback_provider=health.fallback_provider,
        providers=providers,
    )


async def _check_db(session: DBSession) -> bool:
    try:
        await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
