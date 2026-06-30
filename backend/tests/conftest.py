"""Shared pytest fixtures.

Sets the environment to `testing` before importing the app and exposes an
async HTTP client bound to the ASGI app (no network / no DB required for the
Sprint 0 foundation endpoints).
"""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio

# Ensure the sibling `ai` package (repo root) is importable in tests.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("APP_ENV", "testing")

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.main import create_app  # noqa: E402


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Yield an AsyncClient wired to the FastAPI app via ASGI transport."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
